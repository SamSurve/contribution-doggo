"""
Contribution data fetcher for Contribution Doggo.
Supports GitHub GraphQL API with token, public contributions endpoint fallback,
and offline mock calendar for testing.
"""
from __future__ import annotations

import os
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

import requests


def fetch_contributions(
    username: str = "SamSurve",
    token: str | None = None
) -> Tuple[Dict[Tuple[int, int], Dict[str, Any]], List[Dict[str, Any]], int, Dict[str, Any] | None]:
    """
    Fetches the 53x7 contribution calendar for the given username.
    Returns:
        (grid_days, active_days, total_contributions, brightest_day)
    """
    auth_token = token or os.getenv("DOGGO_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

    # 1. Attempt GraphQL API if token is provided
    if auth_token:
        try:
            query = """
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
                }
              }
            }
            """
            resp = requests.post(
                "https://api.github.com/graphql",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"query": query, "variables": {"login": username}},
                timeout=20,
            )
            if resp.status_code == 200:
                payload = resp.json()
                user = payload.get("data", {}).get("user")
                if user:
                    cal = user["contributionsCollection"]["contributionCalendar"]
                    weeks_data = cal["weeks"]
                    level_map = {
                        "NONE": 0,
                        "FIRST_QUARTILE": 1,
                        "SECOND_QUARTILE": 2,
                        "THIRD_QUARTILE": 3,
                        "FOURTH_QUARTILE": 4,
                    }
                    grid_days: Dict[Tuple[int, int], Dict[str, Any]] = {}
                    active_days: List[Dict[str, Any]] = []

                    # Keep last 53 weeks
                    for c_idx, wk in enumerate(weeks_data[-53:]):
                        for day in wk["contributionDays"]:
                            r_idx = int(day["weekday"])
                            cnt = int(day["contributionCount"])
                            lvl = level_map.get(day.get("contributionLevel", "NONE"), 0)
                            if cnt > 0 and lvl == 0:
                                lvl = 1
                            item = {
                                "date": day["date"],
                                "row": r_idx,
                                "col": c_idx,
                                "count": cnt,
                                "level": lvl,
                            }
                            grid_days[(c_idx, r_idx)] = item
                            if cnt > 0:
                                active_days.append(item)

                    total = int(cal.get("totalContributions", sum(d["count"] for d in grid_days.values())))
                    brightest = max(active_days, key=lambda x: x["count"]) if active_days else None
                    return grid_days, active_days, total, brightest
        except Exception:
            # Fall through to web endpoint
            pass

    # 2. Public web endpoint fallback
    try:
        url = f"https://github.com/users/{username}/contributions"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        if r.status_code == 200:
            matches = re.findall(
                r'id="contribution-day-component-(\d+)-(\d+)"\s+data-level="(\d+)"[^>]*data-date="([0-9-]+)"',
                r.text,
            )
            if not matches:
                matches = re.findall(
                    r'data-date="([0-9-]+)"[^>]*id="contribution-day-component-(\d+)-(\d+)"[^>]*data-level="(\d+)"',
                    r.text,
                )
                if matches:
                    matches = [(m[1], m[2], m[3], m[0]) for m in matches]

            tooltip_map: Dict[str, int] = {}
            for m in re.finditer(r'for="(contribution-day-component-\d+-\d+)"[^>]*>\s*([0-9]+|No)\s+contribution', r.text):
                day_id = m.group(1)
                cnt_str = m.group(2)
                cnt = 0 if cnt_str == "No" else int(cnt_str)
                tooltip_map[day_id] = cnt

            grid_days = {}
            active_days = []
            for row_s, col_s, lvl_s, dt_s in matches:
                r_i, c_i, l_i = int(row_s), int(col_s), int(lvl_s)
                day_id = f"contribution-day-component-{row_s}-{col_s}"
                cnt = tooltip_map.get(day_id, l_i)
                item = {
                    "date": dt_s,
                    "row": r_i,
                    "col": c_i,
                    "count": cnt,
                    "level": l_i,
                }
                grid_days[(c_i, r_i)] = item
                if cnt > 0:
                    active_days.append(item)

            total = sum(d["count"] for d in grid_days.values())
            brightest = max(active_days, key=lambda x: x["count"]) if active_days else None
            return grid_days, active_days, total, brightest
    except Exception:
        pass

    # 3. Synthetic rolling calendar fallback (for offline tests)
    today = date.today()
    start_date = today - timedelta(days=52 * 7 + today.weekday())
    grid_days = {}
    active_days = []

    for c in range(53):
        for r in range(7):
            curr_date = start_date + timedelta(days=c * 7 + r)
            dt_s = curr_date.isoformat()
            cnt = 0
            lvl = 0
            # A few synthetic clusters
            if c in (46, 47, 50, 51) and r in (0, 2, 4, 5):
                cnt = 12 if (c == 47 and r == 0) else 5
                lvl = 4 if cnt > 10 else 2
            item = {"date": dt_s, "row": r, "col": c, "count": cnt, "level": lvl}
            grid_days[(c, r)] = item
            if cnt > 0:
                active_days.append(item)

    total = sum(d["count"] for d in grid_days.values())
    brightest = max(active_days, key=lambda x: x["count"]) if active_days else None
    return grid_days, active_days, total, brightest
