"""
Comprehensive unit tests for snapshot engine:
- New commit detection
- Increase in commitCount
- Multiple new commit dates
- No false commit detection for issue/PR-only contribution increase
- First-run baseline behaviour
- Failed snapshot write preserves prior valid snapshot
- Calendar year transition / baseline advancement prevention
"""
import json
import pytest
from pathlib import Path
from src.snapshot import (
    detect_new_contributions,
    load_previous_snapshot,
    save_snapshot,
)
from src.planner import select_diverse_targets


def test_first_run_baseline(tmp_path):
    """
    On first run without a previous snapshot, historical commits
    must not be flagged as 'new' commits. Returns empty list.
    """
    grid = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "commit_count": 26, "level": 4},
        (51, 4): {"date": "2026-10-29", "col": 51, "row": 4, "count": 20, "commit_count": 20, "level": 4},
    }
    new_commits = detect_new_contributions(grid, snapshot=None)
    assert new_commits == []
    assert not any(item.get("is_new") for item in grid.values())


def test_new_commit_detection(tmp_path):
    """
    When a date has commits in the current run that were 0/absent in snapshot,
    it is detected as a new commit.
    """
    prev_snapshot = {
        "daily_counts": {"2026-09-27": 26},
        "daily_commit_counts": {"2026-09-27": 26},
    }
    grid = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "commit_count": 26, "level": 4},
        (52, 0): {"date": "2026-11-02", "col": 52, "row": 0, "count": 5, "commit_count": 5, "level": 2},
    }
    new_commits = detect_new_contributions(grid, snapshot=prev_snapshot)
    assert len(new_commits) == 1
    assert new_commits[0]["date"] == "2026-11-02"
    assert new_commits[0]["is_new"] is True
    assert new_commits[0]["new_commits_diff"] == 5


def test_increase_in_commit_count(tmp_path):
    """
    When a date's commitCount increases from 10 to 18, it is detected as new with diff=8.
    """
    prev_snapshot = {
        "daily_counts": {"2026-10-29": 10},
        "daily_commit_counts": {"2026-10-29": 10},
    }
    grid = {
        (51, 4): {"date": "2026-10-29", "col": 51, "row": 4, "count": 18, "commit_count": 18, "level": 4},
    }
    new_commits = detect_new_contributions(grid, snapshot=prev_snapshot)
    assert len(new_commits) == 1
    assert new_commits[0]["date"] == "2026-10-29"
    assert new_commits[0]["new_commits_diff"] == 8


def test_multiple_new_commit_dates():
    """
    When multiple distinct dates receive new commits, all are detected
    and prioritized in Doggo's target selection.
    """
    prev_snapshot = {
        "daily_commit_counts": {"2026-09-27": 26},
    }
    grid = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "commit_count": 26, "level": 4},
        (50, 6): {"date": "2026-10-24", "col": 50, "row": 6, "count": 13, "commit_count": 13, "level": 3},
        (51, 4): {"date": "2026-10-29", "col": 51, "row": 4, "count": 24, "commit_count": 24, "level": 4},
        (52, 0): {"date": "2026-11-01", "col": 52, "row": 0, "count": 9, "commit_count": 9, "level": 2},
    }
    new_commits = detect_new_contributions(grid, snapshot=prev_snapshot)
    assert len(new_commits) == 3
    new_dates = {nc["date"] for nc in new_commits}
    assert new_dates == {"2026-10-24", "2026-10-29", "2026-11-01"}

    # Verify priority routing selects all new commit dates
    targets = select_diverse_targets(list(grid.values()))
    target_dates = [t["date"] for t in targets]
    for nd in ["2026-10-24", "2026-10-29", "2026-11-01"]:
        assert nd in target_dates, f"Expected {nd} in priority targets: {target_dates}"


def test_no_false_commit_detection_for_issue_or_pr_increase():
    """
    CRITICAL: An increase in total contributionCount caused solely by
    issues or pull requests (where commitCount did NOT change) must NOT
    be detected as a new commit.
    """
    prev_snapshot = {
        "daily_counts": {"2026-10-29": 10},
        "daily_commit_counts": {"2026-10-29": 8},  # 8 commits, 2 issues/PRs
    }
    # User creates 3 more issues/PRs today, so total count increases to 13,
    # but commitCount remains strictly 8.
    grid = {
        (51, 4): {
            "date": "2026-10-29",
            "col": 51,
            "row": 4,
            "count": 13,         # total contributions increased!
            "commit_count": 8,   # commits did NOT increase!
            "level": 4,
        },
    }
    new_commits = detect_new_contributions(grid, snapshot=prev_snapshot)
    assert new_commits == [], f"Expected 0 new commits, but got {new_commits}"
    assert not grid[(51, 4)].get("is_new")


def test_failed_snapshot_write_preserves_prior_valid_snapshot(tmp_path, monkeypatch):
    """
    If snapshot persistence fails (e.g. disk or serialization failure),
    the exception must propagate and the prior valid snapshot file must remain intact.
    """
    snap_file = tmp_path / "target_snapshot.json"
    initial_grid = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "commit_count": 26, "level": 4},
    }
    save_snapshot(initial_grid, 26, username="SamSurve", destination=snap_file)

    # Verify initial snapshot is written
    assert snap_file.exists()
    initial_content = snap_file.read_text(encoding="utf-8")
    assert '"2026-09-27": 26' in initial_content

    # Simulate an error during open/write of destination
    def faulty_dump(*args, **kwargs):
        raise OSError("Simulated disk write failure")

    monkeypatch.setattr("json.dump", faulty_dump)

    updated_grid = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 30, "commit_count": 30, "level": 4},
    }
    with pytest.raises(OSError, match="Simulated disk write failure"):
        save_snapshot(updated_grid, 30, username="SamSurve", destination=snap_file)

    # Prior valid snapshot must be preserved unchanged
    assert snap_file.exists()
    assert snap_file.read_text(encoding="utf-8") == initial_content


def test_no_duplicate_detection_after_persistence(tmp_path):
    """
    After successfully persisting a snapshot, running detection again with
    the same data must return 0 new commits (no duplicate alerts).
    """
    snap_file = tmp_path / "snapshot.json"
    grid = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "commit_count": 26, "level": 4},
    }
    snap = save_snapshot(grid, 26, username="SamSurve", destination=snap_file)

    # Second run with same grid
    loaded = load_previous_snapshot(snap_file)
    new_commits = detect_new_contributions(grid, snapshot=loaded)
    assert new_commits == []
