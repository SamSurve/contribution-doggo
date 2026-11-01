"""
Tests for contribution data fetching, snapshot persistence, and future contribution compatibility.
"""
import pytest
from datetime import date, timedelta
from src.fetcher import fetch_contributions
from src.planner import build_timeline, select_diverse_targets
from src.snapshot import detect_new_contributions, load_previous_snapshot, save_snapshot


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

    # The new peak day must be dynamically selected
    assert any(t["date"] == "2026-11-02" and t["count"] == 50 for t in targets_updated)

    # Generate timeline with new contribution
    timeline = build_timeline({}, new_active, 100, targets_updated[0])
    assert any(t["date"] == "2026-11-02" for f in timeline if f.get("target") for t in [f["target"]])


def test_snapshot_new_commit_detection_and_priority(tmp_path):
    """
    Verify that newly detected commits from previous snapshot comparison
    become priority targets for Doggo.
    """
    snap_file = tmp_path / "snap.json"

    # Base grid
    grid = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "level": 4},
        (51, 4): {"date": "2026-10-29", "col": 51, "row": 4, "count": 20, "level": 4},
    }
    save_snapshot(grid, 46, username="SamSurve", destination=snap_file)

    # Loaded snapshot
    loaded = load_previous_snapshot(snap_file)
    assert loaded is not None
    assert loaded["daily_counts"]["2026-09-27"] == 26

    # New day with commits detected
    updated_grid = dict(grid)
    updated_grid[(52, 0)] = {"date": "2026-11-02", "col": 52, "row": 0, "count": 5, "level": 2}

    new_commits = detect_new_contributions(updated_grid, loaded)
    assert len(new_commits) == 1
    assert new_commits[0]["date"] == "2026-11-02"
    assert new_commits[0]["is_new"] is True

    # Check that new commit becomes priority target
    active_days = list(updated_grid.values())
    targets = select_diverse_targets(active_days)
    assert any(t["date"] == "2026-11-02" and t.get("is_new") for t in targets)
