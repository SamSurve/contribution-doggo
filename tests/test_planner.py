"""
Tests for pathfinding, target selection, and timeline generation.
"""
from src.planner import build_timeline, select_diverse_targets, WEEKS, GX, GY, STEP, CELL


def test_diverse_targets_selection():
    sample_active = [
        {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "level": 4},
        {"date": "2026-10-02", "col": 47, "row": 5, "count": 17, "level": 3},
        {"date": "2026-10-29", "col": 51, "row": 4, "count": 24, "level": 4},
        {"date": "2026-11-01", "col": 52, "row": 0, "count": 9, "level": 2},
    ]
    targets = select_diverse_targets(sample_active)
    assert len(targets) >= 3
    # Check that rows are diverse
    rows = [t["row"] for t in targets]
    assert len(set(rows)) >= 2, f"Expected diverse rows, got {rows}"
    # Peak day must be visited
    assert any(t["count"] == 26 for t in targets)


def test_timeline_loop_continuity():
    sample_active = [
        {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "level": 4},
        {"date": "2026-10-29", "col": 51, "row": 4, "count": 24, "level": 4},
    ]
    timeline = build_timeline({}, sample_active, 50, sample_active[0])
    assert len(timeline) > 30

    # Start and end frame position continuity
    first_frame = timeline[0]
    last_frame = timeline[-1]
    assert first_frame["x"] == last_frame["x"], "Loop start and end X should match for seamless looping"
    assert first_frame["y"] == last_frame["y"], "Loop start and end Y should match for seamless looping"
    assert first_frame["state"] == "idle"
    assert last_frame["state"] == "idle"


def test_grid_boundaries():
    sample_active = [
        {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "level": 4},
        {"date": "2026-10-29", "col": 51, "row": 6, "count": 24, "level": 4},
    ]
    timeline = build_timeline({}, sample_active, 50, sample_active[0])
    for idx, f in enumerate(timeline):
        # Canvas is W=1100, H=340
        # Card inner area is approx x: 20 to 1080, y: 20 to 320
        assert 20 <= f["x"] <= 1060, f"Frame {idx} X out of bounds: {f['x']}"
        assert 60 <= f["y"] <= 280, f"Frame {idx} Y out of bounds: {f['y']}"


def test_state_transitions():
    sample_active = [
        {"date": "2026-09-27", "col": 47, "row": 0, "count": 26, "level": 4},
    ]
    timeline = build_timeline({}, sample_active, 26, sample_active[0])
    states = [f["state"] for f in timeline]

    # Must contain idle, run, sniff, paw_touch, happy
    assert "idle" in states
    assert "run" in states
    assert "sniff" in states
    assert "paw_touch" in states
    assert "happy" in states
