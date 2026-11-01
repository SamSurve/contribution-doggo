"""
Tests for contribution data fetching, true commit detection,
timezone normalization, pagination, and grid-square mapping.
"""
import pytest
from datetime import date, timedelta
from src.fetcher import (
    aggregate_commit_contributions,
    fetch_contributions,
    fetch_contributions_graphql,
    normalize_occurred_at,
)
from src.planner import build_timeline, select_diverse_targets


def test_synthetic_offline_fallback():
    # Explicitly permitted fallback returns a 53x7 calendar
    grid_days, active_days, total, brightest = fetch_contributions(
        username="mock_user_xyz", token="invalid", allow_synthetic=True
    )
    assert len(grid_days) == 53 * 7
    assert total >= 0


def test_production_rejects_synthetic_fallback(monkeypatch):
    # Production runs must not silently overwrite output with synthetic data
    monkeypatch.delenv("ALLOW_SYNTHETIC", raising=False)
    with pytest.raises(RuntimeError, match="Failed to fetch live contribution data"):
        fetch_contributions(username="mock_user_xyz", token="invalid", allow_synthetic=False)


def test_timezone_and_midnight_boundary_handling():
    """
    OccurredAt timestamps near midnight (+/- UTC shifts)
    must align correctly with the calendar's valid YYYY-MM-DD dates.
    """
    valid_calendar_dates = {"2026-10-28", "2026-10-29", "2026-10-30"}

    # Direct match
    assert normalize_occurred_at("2026-10-29T12:00:00Z", valid_calendar_dates) == "2026-10-29"

    # Shifted UTC time where raw date is outside calendar dates
    # E.g., 2026-10-31T00:05:00Z when 2026-10-30 is the last calendar date
    assert normalize_occurred_at("2026-10-31T00:05:00Z", valid_calendar_dates) == "2026-10-30"

    # E.g., 2026-10-27T23:55:00Z when 2026-10-28 is the first calendar date
    assert normalize_occurred_at("2026-10-27T23:55:00Z", valid_calendar_dates) == "2026-10-28"


def test_aggregate_commit_contributions_multiple_repos():
    """
    Verifies that commitCount values are summed across multiple repositories
    for the same calendar date.
    """
    valid_dates = {"2026-10-29", "2026-10-30"}
    repos_data = [
        {
            "repository": {"nameWithOwner": "SamSurve/RepoA"},
            "contributions": {
                "nodes": [
                    {"occurredAt": "2026-10-29T10:00:00Z", "commitCount": 15, "isRestricted": False},
                    {"occurredAt": "2026-10-30T10:00:00Z", "commitCount": 4, "isRestricted": False},
                ]
            },
        },
        {
            "repository": {"nameWithOwner": "SamSurve/RepoB"},
            "contributions": {
                "nodes": [
                    {"occurredAt": "2026-10-29T15:30:00Z", "commitCount": 9, "isRestricted": False},
                ]
            },
        },
    ]
    daily = aggregate_commit_contributions(repos_data, valid_dates)
    # RepoA (15) + RepoB (9) = 24 on 2026-10-29
    assert daily["2026-10-29"] == 24
    assert daily["2026-10-30"] == 4


def test_correct_grid_square_mapping():
    """
    Every parsed day in grid_days must map to a valid (col, row) coordinate
    within bounds 0 <= col < 53 and 0 <= row < 7.
    """
    grid_days, active_days, total, brightest = fetch_contributions(
        username="mock_user_xyz", token="invalid", allow_synthetic=True
    )
    assert len(grid_days) == 53 * 7
    for (c, r), item in grid_days.items():
        assert 0 <= c < 53, f"Col {c} out of bounds"
        assert 0 <= r < 7, f"Row {r} out of bounds"
        assert item["col"] == c
        assert item["row"] == r
        assert len(item["date"]) == 10
        assert "commit_count" in item


def test_graphql_pagination(monkeypatch):
    """
    Mocks a paginated GraphQL response where a repository's contributions
    has hasNextPage=True, verifying that subsequent pages are requested and aggregated.
    """
    call_count = 0

    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code

        def json(self):
            return self._json

        def raise_for_status(self):
            pass

    page1_data = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {
                        "totalContributions": 25,
                        "weeks": [
                            {
                                "contributionDays": [
                                    {"date": "2026-10-29", "contributionCount": 25, "contributionLevel": "FOURTH_QUARTILE", "weekday": 4}
                                ]
                            }
                        ],
                    },
                    "commitContributionsByRepository": [
                        {
                            "repository": {"nameWithOwner": "SamSurve/LargeRepo"},
                            "contributions": {
                                "nodes": [
                                    {"occurredAt": "2026-10-29T08:00:00Z", "commitCount": 10, "isRestricted": False}
                                ],
                                "pageInfo": {"hasNextPage": True, "endCursor": "cursor_page_2"},
                            },
                        }
                    ],
                }
            }
        }
    }

    page2_data = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "commitContributionsByRepository": [
                        {
                            "repository": {"nameWithOwner": "SamSurve/LargeRepo"},
                            "contributions": {
                                "nodes": [
                                    {"occurredAt": "2026-10-29T14:00:00Z", "commitCount": 15, "isRestricted": False}
                                ],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            },
                        }
                    ]
                }
            }
        }
    }

    def mock_post(self, url, headers=None, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if "cursor" in json.get("variables", {}):
            return MockResponse(page2_data)
        return MockResponse(page1_data)

    import requests
    monkeypatch.setattr(requests.Session, "post", mock_post)

    grid_days, active_days, total, brightest = fetch_contributions_graphql(
        username="SamSurve", token="fake_token"
    )

    assert call_count == 2, f"Expected 2 GraphQL calls for pagination, got {call_count}"
    assert (0, 4) in grid_days
    # Commits from page 1 (10) + page 2 (15) = 25
    assert grid_days[(0, 4)]["commit_count"] == 25


def test_web_fallback_marks_commit_tracking_unavailable(monkeypatch):
    """
    Public web fallback must never equate total contribution counts with commits.
    Must set commit_count=None and commit_tracking_available=False.
    """
    html_sample = """
    <div>
      <td id="contribution-day-component-2-10" data-date="2026-10-25" data-level="3"></td>
      <tool-tip for="contribution-day-component-2-10">8 contributions on October 25, 2026</tool-tip>
    </div>
    """
    class MockWebResponse:
        def __init__(self, text):
            self.text = text
            self.status_code = 200
        def raise_for_status(self):
            pass

    import requests
    monkeypatch.setattr(requests.Session, "get", lambda self, url, headers=None, timeout=None: MockWebResponse(html_sample))

    from src.fetcher import fetch_contributions_web
    res = fetch_contributions_web(username="SamSurve")

    assert res.commit_tracking_available is False
    grid_days, active_days, total, brightest = res
    assert (10, 2) in grid_days
    item = grid_days[(10, 2)]
    assert item["count"] == 8
    # Must NEVER use total contribution count as commit count
    assert item["commit_count"] is None
    assert item["commit_tracking_available"] is False


def test_graphql_pagination_missing_cursor_raises(monkeypatch):
    """
    If hasNextPage is True but endCursor is missing or empty,
    pagination must raise RuntimeError and never silently truncate.
    """
    page_data = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {
                        "totalContributions": 10,
                        "weeks": [{"contributionDays": [{"date": "2026-10-29", "contributionCount": 10, "contributionLevel": "FOURTH_QUARTILE", "weekday": 4}]}],
                    },
                    "commitContributionsByRepository": [
                        {
                            "repository": {"nameWithOwner": "SamSurve/RepoWithBuggyCursor"},
                            "contributions": {
                                "nodes": [{"occurredAt": "2026-10-29T10:00:00Z", "commitCount": 5, "isRestricted": False}],
                                "pageInfo": {"hasNextPage": True, "endCursor": None},  # Missing cursor!
                            },
                        }
                    ],
                }
            }
        }
    }
    class MockResp:
        def __init__(self, d):
            self._d = d
            self.status_code = 200
        def json(self):
            return self._d
        def raise_for_status(self):
            pass

    import requests
    monkeypatch.setattr(requests.Session, "post", lambda self, url, headers=None, json=None, timeout=None: MockResp(page_data))

    with pytest.raises(RuntimeError, match="endCursor is missing or empty"):
        fetch_contributions_graphql(username="SamSurve", token="fake_token")


def test_graphql_pagination_non_advancing_cursor_raises(monkeypatch):
    """
    If endCursor does not advance between pages, pagination must raise RuntimeError.
    """
    page_data = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {
                        "totalContributions": 10,
                        "weeks": [{"contributionDays": [{"date": "2026-10-29", "contributionCount": 10, "contributionLevel": "FOURTH_QUARTILE", "weekday": 4}]}],
                    },
                    "commitContributionsByRepository": [
                        {
                            "repository": {"nameWithOwner": "SamSurve/RepoStuckCursor"},
                            "contributions": {
                                "nodes": [{"occurredAt": "2026-10-29T10:00:00Z", "commitCount": 5, "isRestricted": False}],
                                "pageInfo": {"hasNextPage": True, "endCursor": "stuck_cursor_token"},
                            },
                        }
                    ],
                }
            }
        }
    }
    class MockResp:
        def __init__(self, d):
            self._d = d
            self.status_code = 200
        def json(self):
            return self._d
        def raise_for_status(self):
            pass

    import requests
    # Both initial and subsequent paginate calls return the same endCursor
    monkeypatch.setattr(requests.Session, "post", lambda self, url, headers=None, json=None, timeout=None: MockResp(page_data))

    with pytest.raises(RuntimeError, match="non-advancing endCursor"):
        fetch_contributions_graphql(username="SamSurve", token="fake_token")


def test_graphql_pagination_missing_repo_raises(monkeypatch):
    """
    If the matching repository is missing in the paginated response,
    pagination must raise RuntimeError instead of silently terminating.
    """
    page1_data = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {
                        "totalContributions": 10,
                        "weeks": [{"contributionDays": [{"date": "2026-10-29", "contributionCount": 10, "contributionLevel": "FOURTH_QUARTILE", "weekday": 4}]}],
                    },
                    "commitContributionsByRepository": [
                        {
                            "repository": {"nameWithOwner": "SamSurve/RepoToFind"},
                            "contributions": {
                                "nodes": [{"occurredAt": "2026-10-29T10:00:00Z", "commitCount": 5, "isRestricted": False}],
                                "pageInfo": {"hasNextPage": True, "endCursor": "page_2_cursor"},
                            },
                        }
                    ],
                }
            }
        }
    }
    page2_missing_repo = {
        "data": {
            "user": {
                "contributionsCollection": {
                    # No RepoToFind here!
                    "commitContributionsByRepository": [],
                }
            }
        }
    }
    class MockResp:
        def __init__(self, d):
            self._d = d
            self.status_code = 200
        def json(self):
            return self._d
        def raise_for_status(self):
            pass

    import requests
    def mock_post(self, url, headers=None, json=None, timeout=None):
        if "cursor" in json.get("variables", {}):
            return MockResp(page2_missing_repo)
        return MockResp(page1_data)

    monkeypatch.setattr(requests.Session, "post", mock_post)

    with pytest.raises(RuntimeError, match="matching repository 'SamSurve/RepoToFind' not found"):
        fetch_contributions_graphql(username="SamSurve", token="fake_token")


def test_graphql_pagination_graphql_error_raises(monkeypatch):
    """
    If paginated query returns GraphQL errors, must raise RuntimeError immediately.
    """
    page1_data = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {
                        "totalContributions": 10,
                        "weeks": [{"contributionDays": [{"date": "2026-10-29", "contributionCount": 10, "contributionLevel": "FOURTH_QUARTILE", "weekday": 4}]}],
                    },
                    "commitContributionsByRepository": [
                        {
                            "repository": {"nameWithOwner": "SamSurve/RepoError"},
                            "contributions": {
                                "nodes": [{"occurredAt": "2026-10-29T10:00:00Z", "commitCount": 5, "isRestricted": False}],
                                "pageInfo": {"hasNextPage": True, "endCursor": "page_2_cursor"},
                            },
                        }
                    ],
                }
            }
        }
    }
    page2_error = {
        "errors": [{"message": "Rate limit exceeded during connection pagination"}]
    }
    class MockResp:
        def __init__(self, d):
            self._d = d
            self.status_code = 200
        def json(self):
            return self._d
        def raise_for_status(self):
            pass

    import requests
    def mock_post(self, url, headers=None, json=None, timeout=None):
        if "cursor" in json.get("variables", {}):
            return MockResp(page2_error)
        return MockResp(page1_data)

    monkeypatch.setattr(requests.Session, "post", mock_post)

    with pytest.raises(RuntimeError, match="GraphQL pagination error"):
        fetch_contributions_graphql(username="SamSurve", token="fake_token")
