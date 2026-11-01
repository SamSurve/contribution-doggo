"""
Pathfinding, target selection, and state machine planner for Contribution Doggo.
Ensures newly detected commits become priority destinations visited before
ordinary historical exploration.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Set, Tuple

# Layout constants
GX, GY = 110, 122
CELL, GAP = 12, 4
STEP = CELL + GAP
WEEKS = 53


def select_diverse_targets(active_days: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Selects target squares for Doggo's patrol.
    Priority Rules:
    1. Newly detected commit dates are top-priority destinations.
       If several dates receive new commits, Doggo visits all selected new-commit targets
       before ordinary historical exploration (up to 4 new commit dates).
    2. If fewer than 3 new commit dates exist, supplements with key historical landmarks
       (peak day, diverse-row day, recent active day).
    3. If no new commits exist, performs standard diverse historical exploration.
    """
    if not active_days:
        return [
            {"date": "2026-06-01", "col": 20, "row": 2, "count": 1, "level": 1},
            {"date": "2026-09-01", "col": 35, "row": 4, "count": 3, "level": 2},
            {"date": "2026-10-25", "col": 48, "row": 5, "count": 5, "level": 3},
        ]

    by_date = sorted(active_days, key=lambda x: x["date"])
    peak = max(active_days, key=lambda x: x["count"])
    latest = by_date[-1]

    # Check for newly detected commits
    new_commits = [d for d in active_days if d.get("is_new")]

    if new_commits:
        # Sort new commits chronologically so movement between them flows cleanly
        new_commits.sort(key=lambda x: (x["col"], x["row"]))
        # Select up to 4 new commit dates to maintain ideal animation length
        selected_new = new_commits[:4]
        targets: List[Dict[str, Any]] = list(selected_new)

        # Supplement with historical landmarks if under target capacity
        if len(targets) < 3:
            # Check peak day
            if not any(t["col"] == peak["col"] and t["row"] == peak["row"] for t in targets):
                targets.append(peak)

        if len(targets) < 3:
            # Check diverse row
            diff_row_candidates = [
                d for d in active_days
                if not any(t["col"] == d["col"] and t["row"] == d["row"] for t in targets)
                and abs(d["row"] - targets[0]["row"]) >= 2
            ]
            if diff_row_candidates:
                targets.append(max(diff_row_candidates, key=lambda x: x["count"]))

        return targets

    # Standard historical exploration (no new commits detected)
    diff_row_candidates = [
        d for d in active_days
        if abs(d["row"] - peak["row"]) >= 2 and d["col"] != peak["col"]
    ]
    diff_row = max(diff_row_candidates, key=lambda x: x["count"]) if diff_row_candidates else None
    earlier = by_date[0] if (by_date[0]["col"] != peak["col"] or by_date[0]["row"] != peak["row"]) else None

    pool = [c for c in [earlier, peak, diff_row, latest] if c is not None]
    unique_targets: List[Dict[str, Any]] = []
    for item in pool:
        if not any(t["col"] == item["col"] and t["row"] == item["row"] for t in unique_targets):
            unique_targets.append(item)

    if len(unique_targets) < 3:
        for act in sorted(active_days, key=lambda x: x["count"], reverse=True):
            if not any(t["col"] == act["col"] and t["row"] == act["row"] for t in unique_targets):
                unique_targets.append(act)
                if len(unique_targets) == 3:
                    break

    unique_targets.sort(key=lambda x: (x["col"], x["row"]))
    return unique_targets


def build_timeline(
    grid_days: Dict[Tuple[int, int], Dict[str, Any]],
    active_days: List[Dict[str, Any]],
    total_commits: int,
    peak_day: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    """
    Builds the frame-by-frame state machine timeline for the corgi.
    """
    targets = select_diverse_targets(active_days)
    timeline: List[Dict[str, Any]] = []
    visited_paws: Set[Tuple[int, int]] = set()

    # Initial start position: col 3, row 2
    start_col, start_row = 3, 2
    cur_x = int(GX + start_col * STEP + CELL // 2 - 16)
    cur_y = int(GY + start_row * STEP + CELL - 20)

    # 1. INITIAL IDLE (2 frames)
    for f in range(2):
        timeline.append({
            "x": cur_x,
            "y": cur_y,
            "facing_left": False,
            "state": "idle",
            "frame": f,
            "status": "PATROL: Starting daily inspection of @SamSurve calendar...",
            "target": None,
            "paws": set(visited_paws),
            "sparkle": False,
        })

    # 2. PATROL TO MIDWAY (col 3 -> col 18, 7 frames)
    for s in range(1, 8):
        t = s / 7.0
        c = start_col + (18 - start_col) * t
        r = start_row + (1 - start_row) * t
        timeline.append({
            "x": int(GX + c * STEP + CELL // 2 - 16),
            "y": int(GY + r * STEP + CELL - 20),
            "facing_left": False,
            "state": "run",
            "frame": s % 4,
            "status": "PATROL: Inspecting early year contributions...",
            "target": None,
            "paws": set(visited_paws),
            "sparkle": False,
        })

    # 3. LOOK AROUND PAUSE at col 18 (2 frames)
    stop_x = int(GX + 18 * STEP + CELL // 2 - 16)
    stop_y = int(GY + 1 * STEP + CELL - 20)
    for f in range(2):
        timeline.append({
            "x": stop_x,
            "y": stop_y,
            "facing_left": False,
            "state": "look_around",
            "frame": f,
            "status": "SEARCH: Scent of active commits detected ahead! ✦",
            "target": None,
            "paws": set(visited_paws),
            "sparkle": False,
        })

    # 4. EXPLORATION OF TARGETS
    prev_col, prev_row = 18, 1
    for target in targets:
        t_col, t_row = target["col"], target["row"]
        t_date = target["date"]
        t_count = target["count"]

        dx = t_col - prev_col
        dy = t_row - prev_row
        dist = math.hypot(dx, dy)
        travel_steps = max(5, min(10, int(dist * 0.5) + 3))
        facing_left = (t_col < prev_col)

        is_new = target.get("is_new", False)
        diff = target.get("new_commits_diff", 1)

        heading_status = (
            f"TRACKING: Approaching NEW COMMIT on {t_date} (+{diff})!"
            if is_new
            else f"TRACKING: Approaching contribution square on {t_date}..."
        )

        for s in range(1, travel_steps + 1):
            t = s / float(travel_steps)
            c = prev_col + dx * t
            r = prev_row + dy * t
            timeline.append({
                "x": int(GX + c * STEP + CELL // 2 - 16),
                "y": int(GY + r * STEP + CELL - 20),
                "facing_left": facing_left,
                "state": "run",
                "frame": s % 4,
                "status": heading_status,
                "target": None,
                "paws": set(visited_paws),
                "sparkle": False,
            })

        # Align dog to face the target cell
        t_cell_x = GX + t_col * STEP
        t_cell_y = GY + t_row * STEP

        sniff_facing_left = facing_left
        if t_col < 2:
            sniff_facing_left = True
        elif t_col > 50:
            sniff_facing_left = False

        if sniff_facing_left:
            sniff_x = t_cell_x + CELL + 2
        else:
            sniff_x = t_cell_x - 26
        sniff_y = t_cell_y + CELL - 20

        sniff_status = (
            f"NEW COMMIT: Sniffing fresh commit on {t_date} (+{diff})! ✦"
            if is_new
            else f"SNIFF: Discovered {t_date} · {t_count} contributions! ✦"
        )
        paw_status = (
            f"NEW CODE: Doggo verifying fresh commit on {t_date} 🐾"
            if is_new
            else "PAW TOUCH: Doggo verifying contribution square..."
        )
        stamp_status = (
            f"APPROVED: Fresh commit verified on {t_date}! ⭐"
            if is_new
            else f"APPROVED: Verified {t_date}! Pawprint stamped."
        )

        # Sniff (3 frames)
        for sf in range(3):
            timeline.append({
                "x": sniff_x,
                "y": sniff_y,
                "facing_left": sniff_facing_left,
                "state": "sniff",
                "frame": sf,
                "status": sniff_status,
                "target": target,
                "paws": set(visited_paws),
                "sparkle": True,
            })

        # Paw touch (2 frames)
        for pf in range(2):
            timeline.append({
                "x": sniff_x,
                "y": sniff_y,
                "facing_left": sniff_facing_left,
                "state": "paw_touch",
                "frame": pf,
                "status": paw_status,
                "target": target,
                "paws": set(visited_paws),
                "sparkle": True,
            })

        # Pawprint stamped
        visited_paws.add((t_col, t_row))

        # Happy tail wag (3 frames)
        for hf in range(3):
            timeline.append({
                "x": sniff_x,
                "y": sniff_y,
                "facing_left": sniff_facing_left,
                "state": "happy",
                "frame": hf,
                "status": stamp_status,
                "target": target,
                "paws": set(visited_paws),
                "sparkle": False,
            })

        prev_col, prev_row = t_col, t_row

    # 5. RETURN TO START LOOP (col 3, row 2)
    dx = start_col - prev_col
    dy = start_row - prev_row
    dist = math.hypot(dx, dy)
    ret_steps = max(7, min(12, int(dist * 0.4) + 4))
    facing_left = (start_col < prev_col)

    for s in range(1, ret_steps + 1):
        t = s / float(ret_steps)
        mid_arc = math.sin(t * math.pi) * 2.0
        c = prev_col + dx * t
        r = min(6.0, max(0.0, prev_row + dy * t + mid_arc))
        timeline.append({
            "x": int(GX + c * STEP + CELL // 2 - 16),
            "y": int(GY + r * STEP + CELL - 20),
            "facing_left": facing_left,
            "state": "run",
            "frame": s % 4,
            "status": "PATROL: Patrol loop complete · Guarding contributions...",
            "target": None,
            "paws": set(visited_paws),
            "sparkle": False,
        })

    # Seamless ending idle frame (matches frame 0)
    timeline.append({
        "x": int(GX + start_col * STEP + CELL // 2 - 16),
        "y": int(GY + start_row * STEP + CELL - 20),
        "facing_left": False,
        "state": "idle",
        "frame": 0,
        "status": "PATROL: Starting daily inspection of @SamSurve calendar...",
        "target": None,
        "paws": set(visited_paws),
        "sparkle": False,
    })

    return timeline
