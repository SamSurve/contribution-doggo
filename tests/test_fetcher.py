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
