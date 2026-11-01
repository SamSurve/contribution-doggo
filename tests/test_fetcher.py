"""
Tests for contribution data fetching and future contribution compatibility.
"""
from datetime import date, timedelta
from src.fetcher import fetch_contributions
from src.planner import build_timeline, select_diverse_targets


def test_synthetic_offline_fallback():
    # Calling with empty username or non-existent endpoint uses fallback safely
    grid_days, active_days, total, brightest = fetch_contributions(username="mock_user_xyz", token="invalid")
    assert len(grid_days) == 53 * 7
    assert total >= 0


def test_future_contribution_simulation():
    """
    Simulate future contributions:
    - Newly active squares
    - Increased contribution counts
    - New calendar week
    Verify that targets and timeline recalculate dynamically without code changes.
    """
    base_active = [
        {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "level": 4},
        {"date": "2026-10-29", "col": 51, "row": 4, "count": 24, "level": 4},
    ]
    targets_base = select_diverse_targets(base_active)

    # Tomorrow: user makes a massive 50-commit push on col 52, row 1
    new_active = list(base_active) + [
        {"date": "2026-11-02", "col": 52, "row": 1, "count": 50, "level": 4}
    ]
    targets_updated = select_diverse_targets(new_active)

    # The new peak day must be dynamically selected!
    assert any(t["date"] == "2026-11-02" and t["count"] == 50 for t in targets_updated)

    # Generate timeline with new contribution
    timeline = build_timeline({}, new_active, 100, targets_updated[0])
    assert any(t["date"] == "2026-11-02" for f in timeline if f.get("target") for t in [f["target"]])
