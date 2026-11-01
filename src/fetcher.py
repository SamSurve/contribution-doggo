"""
Contribution data fetcher for Contribution Doggo.
Fetches both contributionCalendar (for square rendering) and
commitContributionsByRepository (for true commit-specific detection).
Supports GraphQL pagination across repositories and contribution connections.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import requests


class ContributionResult(tuple):
    """
    Subclasses 4-tuple (grid_days, active_days, total_contributions, brightest_day)
    while exposing commit_tracking_available attribute for downstream logic.
    """
    grid_days: Dict[Tuple[int, int], Dict[str, Any]]
    active_days: List[Dict[str, Any]]
    total_contributions: int
    brightest_day: Optional[Dict[str, Any]]
    commit_tracking_available: bool

    def __new__(
        cls,
        grid_days: Dict[Tuple[int, int], Dict[str, Any]],
        active_days: List[Dict[str, Any]],
        total_contributions: int,
        brightest_day: Optional[Dict[str, Any]],
        commit_tracking_available: bool = True,
    ):
        obj = super().__new__(cls, (grid_days, active_days, total_contributions, brightest_day))
        obj.grid_days = grid_days
        obj.active_days = active_days
        obj.total_contributions = total_contributions
        obj.brightest_day = brightest_day
        obj.commit_tracking_available = commit_tracking_available
        return obj


GRAPHQL_QUERY_INITIAL = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
            weekday
          }
        }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          nameWithOwner
        }
        contributions(first: 100) {
          nodes {
            occurredAt
            commitCount
            isRestricted
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
  }
}
"""

GRAPHQL_QUERY_PAGINATE_REPO = """
query($login: String!, $cursor: String!) {
  user(login: $login) {
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          nameWithOwner
        }
        contributions(first: 100, after: $cursor) {
          nodes {
            occurredAt
            commitCount
            isRestricted
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
  }
}
"""


def normalize_occurred_at(occurred_at_str: str, valid_calendar_dates: Set[str]) -> str:
    """
    Normalizes an occurredAt ISO-8601 timestamp string into a YYYY-MM-DD date.
    Aligns with GitHub's contributionCalendar dates, handling timezone boundary offsets.
    """
    raw_date = occurred_at_str[:10]
    if raw_date in valid_calendar_dates:
        return raw_date

    # Parse ISO timestamp with timezone awareness
    try:
        clean_str = occurred_at_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
    except Exception:
        return raw_date

    # If raw date is not directly in calendar dates (e.g. UTC shift around midnight),
    # check +/- 1 calendar day
    candidate_prev = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    candidate_next = (dt + timedelta(days=1)).strftime("%Y-%m-%d")

    if candidate_prev in valid_calendar_dates:
        return candidate_prev
    if candidate_next in valid_calendar_dates:
        return candidate_next

    return raw_date


def aggregate_commit_contributions(
    repo_contributions_list: List[Dict[str, Any]],
    valid_calendar_dates: Set[str],
) -> Dict[str, int]:
    """
    Aggregates commitCount across all repositories by normalized date.
    """
    daily_commits: Dict[str, int] = defaultdict(int)

    for repo_entry in repo_contributions_list:
        contrib_conn = repo_entry.get("contributions", {})
        nodes = contrib_conn.get("nodes", [])
        for node in nodes:
            occ_at = node.get("occurredAt")
            if not occ_at:
                continue
            commits = int(node.get("commitCount", 0))
            if commits <= 0:
                continue
            normalized_date = normalize_occurred_at(occ_at, valid_calendar_dates)
            daily_commits[normalized_date] += commits

    return dict(daily_commits)


def fetch_contributions_graphql(
    username: str,
    token: str,
    session: Optional[requests.Session] = None,
) -> Tuple[Dict[Tuple[int, int], Dict[str, Any]], List[Dict[str, Any]], int, Dict[str, Any] | None]:
    """
    Queries GitHub GraphQL API with full repository coverage and pagination.
    """
    s = session or requests.Session()
    headers = {"Authorization": f"Bearer {token}"}

    resp = s.post(
        "https://api.github.com/graphql",
        headers=headers,
        json={"query": GRAPHQL_QUERY_INITIAL, "variables": {"login": username}},
        timeout=25,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL error: {payload['errors']}")

    user_data = payload.get("data", {}).get("user")
    if not user_data:
        raise RuntimeError(f"User @{username} not found in GraphQL response.")

    collec = user_data["contributionsCollection"]
    cal = collec["contributionCalendar"]
    weeks_data = cal["weeks"]

    level_map = {
        "NONE": 0,
        "FIRST_QUARTILE": 1,
        "SECOND_QUARTILE": 2,
        "THIRD_QUARTILE": 3,
        "FOURTH_QUARTILE": 4,
    }

    grid_days: Dict[Tuple[int, int], Dict[str, Any]] = {}
    valid_calendar_dates: Set[str] = set()

    for c_idx, wk in enumerate(weeks_data[-53:]):
        for day in wk["contributionDays"]:
            r_idx = int(day["weekday"])
            cnt = int(day["contributionCount"])
            lvl = level_map.get(day.get("contributionLevel", "NONE"), 0)
            if cnt > 0 and lvl == 0:
                lvl = 1
            d_str = day["date"]
            valid_calendar_dates.add(d_str)
            item = {
                "date": d_str,
                "row": r_idx,
                "col": c_idx,
                "count": cnt,  # Total contributions (issues + PRs + commits)
                "commit_count": 0,  # Will be populated from commitContributionsByRepository
                "commit_tracking_available": True,
                "level": lvl,
            }
            grid_days[(c_idx, r_idx)] = item

    # Collect initial commit contributions by repository
    repo_entries = collec.get("commitContributionsByRepository", [])

    # Check for repositories requiring pagination (more than 100 commit contribution days)
    # Paginate any repository connection that has hasNextPage.
    # Never silently break on failed pagination requests, GraphQL errors, missing matching repos or non-advancing cursors.
    for repo_entry in repo_entries:
        conn = repo_entry.get("contributions", {})
        page_info = conn.get("pageInfo", {})
        repo_name = repo_entry.get("repository", {}).get("nameWithOwner", "unknown")
        prev_cursor = None
        while page_info.get("hasNextPage"):
            cursor = page_info.get("endCursor")
            if not cursor:
                raise RuntimeError(
                    f"GraphQL pagination error for repository '{repo_name}': "
                    "hasNextPage is True but endCursor is missing or empty."
                )
            if cursor == prev_cursor:
                raise RuntimeError(
                    f"GraphQL pagination error for repository '{repo_name}': "
                    f"non-advancing endCursor detected ({cursor})."
                )
            prev_cursor = cursor

            page_resp = s.post(
                "https://api.github.com/graphql",
                headers=headers,
                json={"query": GRAPHQL_QUERY_PAGINATE_REPO, "variables": {"login": username, "cursor": cursor}},
                timeout=25,
            )
            page_resp.raise_for_status()
            page_payload = page_resp.json()
            if page_payload.get("errors"):
                raise RuntimeError(
                    f"GraphQL pagination error for repository '{repo_name}': {page_payload['errors']}"
                )

            page_data = page_payload.get("data", {}).get("user", {}).get("contributionsCollection", {})
            page_repos = page_data.get("commitContributionsByRepository", [])
            # Find matching repo entry in the paginated page
            matched_repo = next(
                (r for r in page_repos if r.get("repository", {}).get("nameWithOwner") == repo_name),
                None,
            )
            if not matched_repo:
                raise RuntimeError(
                    f"GraphQL pagination error: matching repository '{repo_name}' "
                    f"not found in paginated response for cursor '{cursor}'."
                )

            next_conn = matched_repo.get("contributions", {})
            next_nodes = next_conn.get("nodes")
            if next_nodes is None:
                raise RuntimeError(
                    f"GraphQL pagination error for repository '{repo_name}': contributions nodes is None."
                )

            conn["nodes"].extend(next_nodes)
            page_info = next_conn.get("pageInfo", {})

    # Aggregate commitCount values across repositories
    daily_commits = aggregate_commit_contributions(repo_entries, valid_calendar_dates)

    # Populate commit_count on grid days
    active_days: List[Dict[str, Any]] = []
    for item in grid_days.values():
        d_str = item["date"]
        # Populate true commit-specific count
        item["commit_count"] = daily_commits.get(d_str, 0)
        if item["count"] > 0 or item["commit_count"] > 0:
            active_days.append(item)

    total_contributions = int(cal.get("totalContributions", sum(d["count"] for d in grid_days.values())))
    brightest_day = max(active_days, key=lambda x: x["count"]) if active_days else None

    return ContributionResult(
        grid_days, active_days, total_contributions, brightest_day, commit_tracking_available=True
    )


def fetch_contributions_web(
    username: str,
    session: Optional[requests.Session] = None,
) -> ContributionResult:
    """
    Public web fallback for unauthenticated local development.
    Commit-specific tracking is unavailable via public HTML scraping;
    commit_count is explicitly set to None and commit_tracking_available is False.
    Total contribution counts are NEVER equated with commit counts.
    """
    s = session or requests.Session()
    url = f"https://github.com/users/{username}/contributions"
    r = s.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()

    matches: List[Tuple[str, str, str, str]] = []
    for tag in re.finditer(r'<[^>]*id="contribution-day-component-(\d+)-(\d+)"[^>]*>', r.text):
        row_s, col_s = tag.group(1), tag.group(2)
        tag_str = tag.group(0)
        dt_m = re.search(r'data-date="([0-9-]+)"', tag_str)
        lvl_m = re.search(r'data-level="(\d+)"', tag_str)
        if dt_m and lvl_m:
            matches.append((row_s, col_s, lvl_m.group(1), dt_m.group(1)))

    if not matches:
        # Fallback regex for reversed attribute structures
        matches = re.findall(
            r'id="contribution-day-component-(\d+)-(\d+)"\s+data-level="(\d+)"[^>]*data-date="([0-9-]+)"',
            r.text,
        )

    tooltip_map: Dict[str, int] = {}
    for m in re.finditer(r'for="(contribution-day-component-\d+-\d+)"[^>]*>\s*([0-9]+|No)\s+contribution', r.text):
        day_id = m.group(1)
        cnt_str = m.group(2)
        cnt = 0 if cnt_str == "No" else int(cnt_str)
        tooltip_map[day_id] = cnt

    grid_days: Dict[Tuple[int, int], Dict[str, Any]] = {}
    active_days: List[Dict[str, Any]] = []

    for row_s, col_s, lvl_s, dt_s in matches:
        r_i, c_i, l_i = int(row_s), int(col_s), int(lvl_s)
        day_id = f"contribution-day-component-{row_s}-{col_s}"
        cnt = tooltip_map.get(day_id, l_i)
        item = {
            "date": dt_s,
            "row": r_i,
            "col": c_i,
            "count": cnt,
            "commit_count": None,  # NEVER use total contribution counts as commit counts
            "commit_tracking_available": False,
            "level": l_i,
        }
        grid_days[(c_i, r_i)] = item
        if cnt > 0:
            active_days.append(item)

    total = sum(d["count"] for d in grid_days.values())
    brightest = max(active_days, key=lambda x: x["count"]) if active_days else None
    return ContributionResult(grid_days, active_days, total, brightest, commit_tracking_available=False)


def fetch_contributions_synthetic(
) -> ContributionResult:
    """
    Offline synthetic calendar strictly used for isolated unit tests.
    """
    today = date.today()
    start_date = today - timedelta(days=52 * 7 + today.weekday())
    grid_days: Dict[Tuple[int, int], Dict[str, Any]] = {}
    active_days: List[Dict[str, Any]] = []

    for c in range(53):
        for r in range(7):
            curr_date = start_date + timedelta(days=c * 7 + r)
            dt_s = curr_date.isoformat()
            cnt = 0
            lvl = 0
            if c in (46, 47, 50, 51) and r in (0, 2, 4, 5):
                cnt = 12 if (c == 47 and r == 0) else 5
                lvl = 4 if cnt > 10 else 2
            item = {
                "date": dt_s,
                "row": r,
                "col": c,
                "count": cnt,
                "commit_count": cnt,
                "commit_tracking_available": True,
                "level": lvl,
            }
            grid_days[(c, r)] = item
            if cnt > 0:
                active_days.append(item)

    total = sum(d["count"] for d in grid_days.values())
    brightest = max(active_days, key=lambda x: x["count"]) if active_days else None
    return ContributionResult(grid_days, active_days, total, brightest, commit_tracking_available=True)


def fetch_contributions(
    username: str = "SamSurve",
    token: str | None = None,
    allow_synthetic: bool = False,
) -> ContributionResult:
    """
    Primary fetcher dispatch:
    1. Authenticated GraphQL query with commitContributionsByRepository
    2. Public web fallback (marks commit tracking unavailable)
    3. Guarded synthetic fallback (tests only)
    """
    auth_token = token or os.getenv("DOGGO_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

    if auth_token:
        try:
            return fetch_contributions_graphql(username=username, token=auth_token)
        except Exception as exc:
            # Avoid leaking token string in error prints
            print(f"[WARN] GraphQL fetch failed ({type(exc).__name__}: {exc}). Falling back to web endpoint...")

    try:
        return fetch_contributions_web(username=username)
    except Exception as exc:
        print(f"[WARN] Web endpoint fetch failed ({type(exc).__name__}).")

    can_use_synthetic = allow_synthetic or (os.getenv("ALLOW_SYNTHETIC", "").lower() in ("1", "true", "yes"))
    if not can_use_synthetic:
        raise RuntimeError(
            f"Failed to fetch live contribution data from GitHub for @{username}. "
            "Production output will not overwrite with synthetic data."
        )

    return fetch_contributions_synthetic()
