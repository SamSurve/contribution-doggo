"""
Persistent contribution snapshot and new-commit detection engine.
Maintains history across scheduled regenerations to detect fresh commits
and prioritize them as primary targets for Contribution Doggo.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SNAPSHOT_FILE = Path("data/contributions_snapshot.json")
DIST_SNAPSHOT = Path("dist/contributions_snapshot.json")


def load_previous_snapshot(custom_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Loads previous contribution snapshot from data/ or dist/ or output branch.
    """
    candidates = [
        custom_path,
        SNAPSHOT_FILE,
        DIST_SNAPSHOT,
    ]
    for p in candidates:
        if p and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "daily_counts" in data:
                        return data
            except Exception:
                pass
    return None


def detect_new_contributions(
    grid_days: Dict[Tuple[int, int], Dict[str, Any]],
    snapshot: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Compares current grid_days with the previous snapshot.
    Identifies dates with increased contribution counts or newly active squares.
    Marks items in grid_days with 'is_new' = True and 'diff' = added_commits.
    Returns list of newly active / updated contribution days.
    """
    if not snapshot or "daily_counts" not in snapshot:
        return []

    prev_counts: Dict[str, int] = snapshot["daily_counts"]
    newly_detected: List[Dict[str, Any]] = []

    for item in grid_days.values():
        d_str = item["date"]
        cnt = item["count"]
        prev_cnt = prev_counts.get(d_str, 0)
        if cnt > prev_cnt:
            item["is_new"] = True
            item["new_diff"] = cnt - prev_cnt
            newly_detected.append(item)

    # Sort descending by date (most recent new commits first)
    newly_detected.sort(key=lambda x: x["date"], reverse=True)
    return newly_detected


def save_snapshot(
    grid_days: Dict[Tuple[int, int], Dict[str, Any]],
    total_contributions: int,
    username: str = "SamSurve",
    destination: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Saves current contribution snapshot to file for next comparison.
    """
    target = destination or SNAPSHOT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    daily_counts = {item["date"]: item["count"] for item in grid_days.values() if item["count"] > 0}
    snapshot = {
        "username": username,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_contributions": total_contributions,
        "active_days_count": len(daily_counts),
        "daily_counts": daily_counts,
    }

    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        # Also copy to dist/ if dist exists
        if target != DIST_SNAPSHOT:
            DIST_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            with open(DIST_SNAPSHOT, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
    except Exception as exc:
        print(f"[WARN] Failed to write snapshot: {exc}")

    return snapshot
