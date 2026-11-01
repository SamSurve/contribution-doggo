"""
Persistent contribution snapshot and commit-specific detection engine.
Maintains history across scheduled regenerations to detect fresh commits,
prevent false issue/PR detections, and ensure atomic persistence.
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
    Loads previous contribution snapshot from custom path, or data/, or dist/.
    Returns None on first run if no valid snapshot exists.
    """
    candidates = [custom_path] if custom_path is not None else [SNAPSHOT_FILE, DIST_SNAPSHOT]
    for p in candidates:
        if p and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and ("daily_commit_counts" in data or "daily_counts" in data):
                        return data
            except Exception:
                pass
    return None


def detect_new_contributions(
    grid_days: Dict[Tuple[int, int], Dict[str, Any]],
    snapshot: Optional[Dict[str, Any]] = None,
    commit_tracking_available: bool = True,
) -> List[Dict[str, Any]]:
    """
    Compares current grid_days with the previous snapshot.

    Rules:
    - If commit_tracking_available is False or commit counts are missing, returns [] (no detection).
    - First-run baseline: if snapshot is None, returns [] (does not flag historical commits as new).
    - Legacy snapshot migration: if snapshot lacks 'daily_commit_counts', performs a one-time
      baseline migration (returns [] and does NOT classify historical commits as new).
      Never falls back to daily_counts for commit detection.
    - Commit-specific: detects genuinely new commits where current_commit_count > prev_commit_count.
    - Issue/PR isolation: an increase in total contribution count without a commit count increase
      is NOT flagged as a new commit.
    - Marks matching items in grid_days with 'is_new' = True and 'new_commits_diff' = diff.
    - Returns list of newly active / updated commit dates sorted descending.
    """
    if not commit_tracking_available:
        print("[SNAPSHOT] Commit tracking unavailable; skipping new commit detection.")
        return []

    # If any item lacks commit_count (e.g. web fallback), commit data is incomplete/unavailable
    if any(item.get("commit_count") is None for item in grid_days.values()):
        print("[SNAPSHOT] Grid items lack commit counts; skipping new commit detection.")
        return []

    if not snapshot:
        # First-run baseline: do not treat existing calendar history as new commits
        return []

    # Legacy snapshot migration: do NOT fall back to daily_counts (they are different metrics)
    if "daily_commit_counts" not in snapshot:
        print("[SNAPSHOT] Legacy snapshot detected without daily_commit_counts. "
              "Performing one-time baseline migration without false commit alerts.")
        return []

    prev_commit_counts: Dict[str, int] = snapshot.get("daily_commit_counts", {})

    newly_detected: List[Dict[str, Any]] = []

    for item in grid_days.values():
        d_str = item["date"]
        current_commits = int(item.get("commit_count", 0) or 0)
        prev_commits = int(prev_commit_counts.get(d_str, 0) or 0)

        # Genuinely new commits or increased commit count
        if current_commits > prev_commits:
            diff = current_commits - prev_commits
            item["is_new"] = True
            item["new_commits_diff"] = diff
            newly_detected.append(item)

    # Sort descending by date (most recent new commits first)
    newly_detected.sort(key=lambda x: x["date"], reverse=True)
    return newly_detected


def stage_snapshot_data(
    grid_days: Dict[Tuple[int, int], Dict[str, Any]],
    total_contributions: int,
    username: str = "SamSurve",
    commit_tracking_available: bool = True,
) -> Dict[str, Any]:
    """
    Builds and validates the contribution and commit snapshot dictionary in memory.
    Refuses to advance if the calendar grid is empty or commit tracking is incomplete.
    """
    if not grid_days:
        raise RuntimeError("Refusing to advance contribution snapshot: calendar grid is empty.")

    if not commit_tracking_available or any(item.get("commit_count") is None for item in grid_days.values()):
        raise RuntimeError(
            "Refusing to advance contribution snapshot: commit tracking data is unavailable or incomplete."
        )

    daily_counts = {item["date"]: item["count"] for item in grid_days.values() if item["count"] > 0}
    daily_commit_counts = {
        item["date"]: int(item.get("commit_count", 0))
        for item in grid_days.values()
        if int(item.get("commit_count", 0)) > 0
    }
    total_commits = sum(daily_commit_counts.values())

    return {
        "username": username,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_contributions": total_contributions,
        "total_commits": total_commits,
        "active_days_count": len(daily_counts),
        "daily_counts": daily_counts,
        "daily_commit_counts": daily_commit_counts,
    }


def save_snapshot(
    grid_days: Dict[Tuple[int, int], Dict[str, Any]],
    total_contributions: int,
    username: str = "SamSurve",
    destination: Optional[Path] = None,
    commit_tracking_available: bool = True,
) -> Dict[str, Any]:
    """
    Atomically saves current contribution and commit counts to file.
    Refuses to advance if commit tracking data is unavailable or incomplete.
    Propagates any persistence exceptions so failed writes never print success
    or advance stored baselines.

    ISOLATION RULE:
    If destination is provided (e.g. test tmp_path), writes ONLY to that destination.
    It NEVER creates, modifies, or mirrors into production data/ or dist/ snapshot files.
    Mirroring to dist/ is strictly reserved for the primary production snapshot.
    """
    snapshot = stage_snapshot_data(
        grid_days=grid_days,
        total_contributions=total_contributions,
        username=username,
        commit_tracking_available=commit_tracking_available,
    )

    target = destination or SNAPSHOT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write to target file: write to .tmp in same directory, fsync, then atomic replace
    temp_target = target.with_suffix(".tmp")
    with open(temp_target, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_target, target)

    # Mirror to dist/ ONLY when saving the primary production snapshot.
    # Custom test destinations must NEVER create, modify, or mirror into data/ or dist/ production files!
    is_primary_production = (destination is None) or (target.resolve() == SNAPSHOT_FILE.resolve())
    if is_primary_production:
        DIST_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        temp_dist = DIST_SNAPSHOT.with_suffix(".tmp")
        with open(temp_dist, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_dist, DIST_SNAPSHOT)

    return snapshot
