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
import os
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


def test_legacy_snapshot_migration_does_not_flag_historical_commits():
    """
    Legacy snapshots contain 'daily_counts' but lack 'daily_commit_counts'.
    Migration must establish a baseline without falsely classifying the
    entire historical calendar as new commits.
    """
    legacy_snapshot = {
        "username": "SamSurve",
        "total_contributions": 150,
        "daily_counts": {
            "2026-10-24": 13,
            "2026-10-29": 24,
            "2026-11-01": 9,
        },
        # NOTE: daily_commit_counts is deliberately absent (legacy format)
    }
    grid = {
        (50, 6): {"date": "2026-10-24", "col": 50, "row": 6, "count": 13, "commit_count": 10, "level": 3},
        (51, 4): {"date": "2026-10-29", "col": 51, "row": 4, "count": 24, "commit_count": 20, "level": 4},
        (52, 0): {"date": "2026-11-01", "col": 52, "row": 0, "count": 9, "commit_count": 8, "level": 2},
    }
    new_commits = detect_new_contributions(grid, snapshot=legacy_snapshot)
    # Must NOT classify legacy calendar days as new commits
    assert new_commits == []
    assert not any(item.get("is_new") for item in grid.values())


def test_refuse_snapshot_advance_when_commit_tracking_unavailable(tmp_path):
    """
    Never advance the stored baseline when commit tracking data is unavailable
    or incomplete (e.g. web fallback with commit_count=None).
    """
    snap_file = tmp_path / "protected_snapshot.json"
    grid_with_none_commits = {
        (51, 4): {"date": "2026-10-29", "col": 51, "row": 4, "count": 24, "commit_count": None, "level": 4},
    }
    with pytest.raises(RuntimeError, match="Refusing to advance contribution snapshot"):
        save_snapshot(
            grid_with_none_commits,
            24,
            destination=snap_file,
            commit_tracking_available=False,
        )
    assert not snap_file.exists()


def test_detect_new_contributions_disabled_when_tracking_unavailable():
    """
    When commit_tracking_available is False, detect_new_contributions
    safely returns empty list rather than making inaccurate comparisons.
    """
    prev_snapshot = {
        "daily_commit_counts": {"2026-10-29": 5},
    }
    grid = {
        (51, 4): {"date": "2026-10-29", "col": 51, "row": 4, "count": 24, "commit_count": 20, "level": 4},
    }
    new_commits = detect_new_contributions(
        grid, snapshot=prev_snapshot, commit_tracking_available=False
    )
    assert new_commits == []


def test_consecutive_runs_lifecycle(tmp_path):
    """
    Simulates consecutive regeneration runs across multiple cycles:
    - Run 1: initial baseline creation
    - Run 2: consecutive run with zero changes produces 0 new commits
    - Run 3: commits added to existing and new dates produces exact deltas
    - Run 4: consecutive run after persistence produces 0 duplicate alerts
    """
    snap_file = tmp_path / "lifecycle_snapshot.json"

    # Cycle 1: Baseline
    grid_c1 = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "commit_count": 26, "level": 4},
        (50, 2): {"date": "2026-10-20", "col": 50, "row": 2, "count": 10, "commit_count": 10, "level": 3},
    }
    s1 = load_previous_snapshot(snap_file)
    assert s1 is None
    new_c1 = detect_new_contributions(grid_c1, snapshot=s1)
    assert new_c1 == []  # First run baseline
    save_snapshot(grid_c1, 36, username="SamSurve", destination=snap_file)

    # Cycle 2: Immediate consecutive run with identical data
    s2 = load_previous_snapshot(snap_file)
    assert s2 is not None
    assert s2["total_commits"] == 36
    new_c2 = detect_new_contributions(grid_c1, snapshot=s2)
    assert new_c2 == []  # No changes detected

    # Cycle 3: New commits occur on 2026-10-20 (+5 commits) and new date 2026-11-01 (8 commits)
    grid_c3 = {
        (47, 0): {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "commit_count": 26, "level": 4},
        (50, 2): {"date": "2026-10-20", "col": 50, "row": 2, "count": 15, "commit_count": 15, "level": 4},
        (52, 0): {"date": "2026-11-01", "col": 52, "row": 0, "count": 8, "commit_count": 8, "level": 2},
    }
    new_c3 = detect_new_contributions(grid_c3, snapshot=s2)
    assert len(new_c3) == 2
    by_date = {nc["date"]: nc for nc in new_c3}
    assert by_date["2026-10-20"]["new_commits_diff"] == 5
    assert by_date["2026-11-01"]["new_commits_diff"] == 8
    save_snapshot(grid_c3, 49, username="SamSurve", destination=snap_file)

    # Cycle 4: Immediate consecutive run after Cycle 3 persistence
    s4 = load_previous_snapshot(snap_file)
    assert s4["total_commits"] == 49
    new_c4 = detect_new_contributions(grid_c3, snapshot=s4)
    assert new_c4 == []  # Zero duplicates


def test_empty_grid_refuses_snapshot_advancement(tmp_path):
    """
    An empty calendar grid (e.g. from an incomplete GraphQL response)
    must raise RuntimeError and refuse to overwrite the stored snapshot.
    """
    snap_file = tmp_path / "empty_grid_test.json"
    with pytest.raises(RuntimeError, match="calendar grid is empty"):
        save_snapshot({}, 0, destination=snap_file)
    assert not snap_file.exists()


def test_custom_test_snapshot_cannot_contaminate_production_files(tmp_path):
    """
    FIX 1 REGRESSION: Custom test snapshot destinations must NEVER create,
    replace, or modify production files at data/ or dist/.
    """
    from src.snapshot import DIST_SNAPSHOT, SNAPSHOT_FILE

    # Capture original production states if files exist
    prod_data_exists = SNAPSHOT_FILE.is_file()
    prod_dist_exists = DIST_SNAPSHOT.is_file()
    orig_data_bytes = SNAPSHOT_FILE.read_bytes() if prod_data_exists else None
    orig_dist_bytes = DIST_SNAPSHOT.read_bytes() if prod_dist_exists else None

    custom_dest = tmp_path / "isolated_test_snapshot.json"
    grid = {
        (0, 0): {"date": "2026-11-01", "row": 0, "col": 0, "count": 999, "commit_count": 999, "level": 4}
    }

    # Save to custom destination
    save_snapshot(grid, 999, username="IsolatedTestUser", destination=custom_dest)

    # 1. Custom destination was written
    assert custom_dest.is_file()
    assert '"IsolatedTestUser"' in custom_dest.read_text(encoding="utf-8")

    # 2. Production data snapshot must be completely untouched
    if prod_data_exists:
        assert SNAPSHOT_FILE.read_bytes() == orig_data_bytes
    else:
        assert not SNAPSHOT_FILE.is_file()

    # 3. Production dist snapshot must be completely untouched (no auto-mirroring)
    if prod_dist_exists:
        assert DIST_SNAPSHOT.read_bytes() == orig_dist_bytes
    else:
        assert not DIST_SNAPSHOT.is_file()

    # 4. load_previous_snapshot() without custom path must NOT load test snapshot
    default_loaded = load_previous_snapshot()
    if default_loaded:
        assert default_loaded.get("username") != "IsolatedTestUser"


def _setup_isolated_workspace(tmp_path):
    """Helper to set up isolated GIF and snapshot files for transactional testing."""
    test_gif = tmp_path / "contribution-doggo.gif"
    test_data = tmp_path / "data" / "contributions_snapshot.json"
    test_dist = tmp_path / "dist" / "contributions_snapshot.json"

    test_gif.parent.mkdir(parents=True, exist_ok=True)
    test_data.parent.mkdir(parents=True, exist_ok=True)
    test_dist.parent.mkdir(parents=True, exist_ok=True)

    gif_bytes = b"ORIGINAL_VALID_GIF_BYTES_1234567890"
    data_bytes = b'{"original": "data_snapshot_bytes"}'
    dist_bytes = b'{"original": "dist_snapshot_bytes"}'

    test_gif.write_bytes(gif_bytes)
    test_data.write_bytes(data_bytes)
    test_dist.write_bytes(dist_bytes)

    return test_gif, test_data, test_dist, gif_bytes, data_bytes, dist_bytes


def _mock_valid_render_gif(**kwargs):
    from PIL import Image as PILImage
    out_p = kwargs["output_path"]
    frames = [PILImage.new("RGB", (10, 10), (i * 10, i * 10, 0)) for i in range(15)]
    frames[0].save(out_p, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)


def test_transactional_rollback_on_gif_rendering_failure(tmp_path, monkeypatch):
    """Rollback test: failure during GIF rendering preserves all original files."""
    import doggo
    test_gif, test_data, test_dist, orig_gif, orig_data, orig_dist = _setup_isolated_workspace(tmp_path)

    monkeypatch.setattr(doggo, "OUTPUT_PATH", str(test_gif))
    monkeypatch.setenv("SNAPSHOT_PATH", str(test_data))
    monkeypatch.setenv("DIST_SNAPSHOT_PATH", str(test_dist))

    from src.fetcher import ContributionResult
    sample_grid = {(0, 0): {"date": "2026-11-01", "row": 0, "col": 0, "count": 1, "commit_count": 1, "level": 1}}
    monkeypatch.setattr(
        doggo, "fetch_contributions",
        lambda *args, **kwargs: ContributionResult(sample_grid, list(sample_grid.values()), 1, None, True)
    )

    def failing_render(**kwargs):
        raise RuntimeError("Simulated render engine crash")

    monkeypatch.setattr(doggo, "render_gif", failing_render)

    exit_code = doggo.main()
    assert exit_code == 1

    # Byte-for-byte identical verification
    assert test_gif.read_bytes() == orig_gif
    assert test_data.read_bytes() == orig_data
    assert test_dist.read_bytes() == orig_dist

    # No leftover temporary or backup files
    for f in tmp_path.glob("**/*"):
        assert not f.name.endswith(".tmp")
        assert not f.name.endswith(".tmp.gif")
        assert not f.name.endswith(".bak")


def test_transactional_rollback_on_snapshot_staging_failure(tmp_path, monkeypatch):
    """Rollback test: failure during snapshot staging restores all original files."""
    import doggo
    test_gif, test_data, test_dist, orig_gif, orig_data, orig_dist = _setup_isolated_workspace(tmp_path)

    monkeypatch.setattr(doggo, "OUTPUT_PATH", str(test_gif))
    monkeypatch.setenv("SNAPSHOT_PATH", str(test_data))
    monkeypatch.setenv("DIST_SNAPSHOT_PATH", str(test_dist))

    from src.fetcher import ContributionResult
    sample_grid = {(0, 0): {"date": "2026-11-01", "row": 0, "col": 0, "count": 1, "commit_count": 1, "level": 1}}
    monkeypatch.setattr(
        doggo, "fetch_contributions",
        lambda *args, **kwargs: ContributionResult(sample_grid, list(sample_grid.values()), 1, None, True)
    )
    monkeypatch.setattr(doggo, "render_gif", _mock_valid_render_gif)

    def failing_stage(*args, **kwargs):
        raise RuntimeError("Simulated staging memory serialization failure")

    monkeypatch.setattr(doggo, "stage_snapshot_data", failing_stage)

    exit_code = doggo.main()
    assert exit_code == 1

    assert test_gif.read_bytes() == orig_gif
    assert test_data.read_bytes() == orig_data
    assert test_dist.read_bytes() == orig_dist

    for f in tmp_path.glob("**/*"):
        assert not f.name.endswith(".tmp")
        assert not f.name.endswith(".tmp.gif")
        assert not f.name.endswith(".bak")


def test_transactional_rollback_on_gif_promotion_failure(tmp_path, monkeypatch):
    """Rollback test: failure when promoting GIF replaces/restores original state."""
    import doggo
    test_gif, test_data, test_dist, orig_gif, orig_data, orig_dist = _setup_isolated_workspace(tmp_path)

    monkeypatch.setattr(doggo, "OUTPUT_PATH", str(test_gif))
    monkeypatch.setenv("SNAPSHOT_PATH", str(test_data))
    monkeypatch.setenv("DIST_SNAPSHOT_PATH", str(test_dist))

    from src.fetcher import ContributionResult
    sample_grid = {(0, 0): {"date": "2026-11-01", "row": 0, "col": 0, "count": 1, "commit_count": 1, "level": 1}}
    monkeypatch.setattr(
        doggo, "fetch_contributions",
        lambda *args, **kwargs: ContributionResult(sample_grid, list(sample_grid.values()), 1, None, True)
    )
    monkeypatch.setattr(doggo, "render_gif", _mock_valid_render_gif)

    real_replace = os.replace
    def failing_replace(src, dst):
        if str(dst) == str(test_gif):
            raise OSError("Simulated permission failure replacing GIF file")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_replace)

    exit_code = doggo.main()
    assert exit_code == 1

    assert test_gif.read_bytes() == orig_gif
    assert test_data.read_bytes() == orig_data
    assert test_dist.read_bytes() == orig_dist

    for f in tmp_path.glob("**/*"):
        assert not f.name.endswith(".tmp")
        assert not f.name.endswith(".tmp.gif")
        assert not f.name.endswith(".bak")


def test_transactional_rollback_on_data_snapshot_promotion_failure(tmp_path, monkeypatch):
    """Rollback test: failure when promoting data snapshot rolls back already-promoted GIF."""
    import doggo
    test_gif, test_data, test_dist, orig_gif, orig_data, orig_dist = _setup_isolated_workspace(tmp_path)

    monkeypatch.setattr(doggo, "OUTPUT_PATH", str(test_gif))
    monkeypatch.setenv("SNAPSHOT_PATH", str(test_data))
    monkeypatch.setenv("DIST_SNAPSHOT_PATH", str(test_dist))

    from src.fetcher import ContributionResult
    sample_grid = {(0, 0): {"date": "2026-11-01", "row": 0, "col": 0, "count": 1, "commit_count": 1, "level": 1}}
    monkeypatch.setattr(
        doggo, "fetch_contributions",
        lambda *args, **kwargs: ContributionResult(sample_grid, list(sample_grid.values()), 1, None, True)
    )
    monkeypatch.setattr(doggo, "render_gif", _mock_valid_render_gif)

    real_replace = os.replace
    def failing_replace(src, dst):
        if str(dst) == str(test_data):
            raise OSError("Simulated permission failure replacing data snapshot")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_replace)

    exit_code = doggo.main()
    assert exit_code == 1

    # GIF must be rolled back to original valid state!
    assert test_gif.read_bytes() == orig_gif
    assert test_data.read_bytes() == orig_data
    assert test_dist.read_bytes() == orig_dist

    for f in tmp_path.glob("**/*"):
        assert not f.name.endswith(".tmp")
        assert not f.name.endswith(".tmp.gif")
        assert not f.name.endswith(".bak")


def test_transactional_rollback_on_dist_snapshot_promotion_failure(tmp_path, monkeypatch):
    """Rollback test: failure when promoting dist snapshot rolls back both GIF and data snapshot."""
    import doggo
    test_gif, test_data, test_dist, orig_gif, orig_data, orig_dist = _setup_isolated_workspace(tmp_path)

    monkeypatch.setattr(doggo, "OUTPUT_PATH", str(test_gif))
    monkeypatch.setenv("SNAPSHOT_PATH", str(test_data))
    monkeypatch.setenv("DIST_SNAPSHOT_PATH", str(test_dist))

    from src.fetcher import ContributionResult
    sample_grid = {(0, 0): {"date": "2026-11-01", "row": 0, "col": 0, "count": 1, "commit_count": 1, "level": 1}}
    monkeypatch.setattr(
        doggo, "fetch_contributions",
        lambda *args, **kwargs: ContributionResult(sample_grid, list(sample_grid.values()), 1, None, True)
    )
    monkeypatch.setattr(doggo, "render_gif", _mock_valid_render_gif)

    real_replace = os.replace
    def failing_replace(src, dst):
        if str(dst) == str(test_dist):
            raise OSError("Simulated permission failure replacing dist snapshot")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_replace)

    exit_code = doggo.main()
    assert exit_code == 1

    assert test_gif.read_bytes() == orig_gif
    assert test_data.read_bytes() == orig_data
    assert test_dist.read_bytes() == orig_dist

    for f in tmp_path.glob("**/*"):
        assert not f.name.endswith(".tmp")
        assert not f.name.endswith(".tmp.gif")
        assert not f.name.endswith(".bak")


def test_successful_complete_transaction(tmp_path, monkeypatch):
    """Transaction success test: all artifacts promoted and backups cleanly removed."""
    import doggo
    test_gif, test_data, test_dist, orig_gif, orig_data, orig_dist = _setup_isolated_workspace(tmp_path)

    monkeypatch.setattr(doggo, "OUTPUT_PATH", str(test_gif))
    monkeypatch.setenv("SNAPSHOT_PATH", str(test_data))
    monkeypatch.setenv("DIST_SNAPSHOT_PATH", str(test_dist))

    from src.fetcher import ContributionResult
    sample_grid = {(0, 0): {"date": "2026-11-01", "row": 0, "col": 0, "count": 5, "commit_count": 5, "level": 2}}
    monkeypatch.setattr(
        doggo, "fetch_contributions",
        lambda *args, **kwargs: ContributionResult(sample_grid, list(sample_grid.values()), 5, None, True)
    )
    monkeypatch.setattr(doggo, "render_gif", _mock_valid_render_gif)

    exit_code = doggo.main()
    assert exit_code == 0

    # Promoted files have new content
    assert test_gif.read_bytes() != orig_gif
    assert test_data.read_bytes() != orig_data
    assert test_dist.read_bytes() != orig_dist
    assert b'"total_contributions": 5' in test_data.read_bytes()
    assert b'"total_contributions": 5' in test_dist.read_bytes()

    # Backups and temporary files removed
    for f in tmp_path.glob("**/*"):
        assert not f.name.endswith(".tmp")
        assert not f.name.endswith(".tmp.gif")
        assert not f.name.endswith(".bak")


def test_safe_early_error_handling_before_rendering(tmp_path, monkeypatch, capsys):
    """
    FIX 3 REGRESSION: Early network/API failure before rendering starts
    must exit cleanly with code 1, preserve all files, leave no temporary files,
    and avoid UnboundLocalError in exception handler.
    """
    import doggo
    test_gif, test_data, test_dist, orig_gif, orig_data, orig_dist = _setup_isolated_workspace(tmp_path)

    monkeypatch.setattr(doggo, "OUTPUT_PATH", str(test_gif))
    monkeypatch.setenv("SNAPSHOT_PATH", str(test_data))
    monkeypatch.setenv("DIST_SNAPSHOT_PATH", str(test_dist))

    def failing_fetch(*args, **kwargs):
        raise RuntimeError("GitHub API network connection refused")

    monkeypatch.setattr(doggo, "fetch_contributions", failing_fetch)

    # Must exit cleanly with return code 1, without UnboundLocalError
    exit_code = doggo.main()
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Generation failed: GitHub API network connection refused" in captured.err

    # Previous files must remain completely unchanged
    assert test_gif.read_bytes() == orig_gif
    assert test_data.read_bytes() == orig_data
    assert test_dist.read_bytes() == orig_dist

    # Zero temporary or backup files left behind
    for f in tmp_path.glob("**/*"):
        assert not f.name.endswith(".tmp")
        assert not f.name.endswith(".tmp.gif")
        assert not f.name.endswith(".bak")
