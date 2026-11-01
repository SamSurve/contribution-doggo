#!/usr/bin/env python3
"""
Contribution Doggo
A premium animated pixel-art corgi companion living inside your GitHub contribution calendar.
"""
from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path

# Ensure UTF-8 output encoding on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.fetcher import fetch_contributions
from src.planner import build_timeline
from src.renderer import render_gif
from src.snapshot import detect_new_contributions, load_previous_snapshot, save_snapshot

USERNAME = os.getenv("GITHUB_USERNAME", "SamSurve")
TOKEN = os.getenv("DOGGO_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "dist/contribution-doggo.gif")


def main() -> int:
    out_file = Path(OUTPUT_PATH)
    backup_file = out_file.with_suffix(".gif.bak")
    has_backup = False

    try:
        # 1. Load previous contribution snapshot for diff detection
        prev_snapshot = load_previous_snapshot()
        if prev_snapshot:
            print(f"[SNAPSHOT] Loaded previous snapshot ({prev_snapshot.get('total_contributions')} total commits).")

        # 2. Fetch live contribution calendar (protects against synthetic mock overwrite)
        print(f"[DOGGO] Fetching GitHub contributions for @{USERNAME}...")
        grid_days, active_days, total_commits, peak_day = fetch_contributions(
            username=USERNAME, token=TOKEN, allow_synthetic=False
        )
        print(f"[OK] Fetched {len(grid_days)} days ({len(active_days)} active). Total contributions: {total_commits}.")
        if peak_day:
            print(f"[OK] Peak day: {peak_day['date']} with {peak_day['count']} commits.")

        # 3. Detect newly added commits since previous snapshot
        new_commits = detect_new_contributions(grid_days, prev_snapshot)
        if new_commits:
            print(f"[NEW COMMITS] Detected {len(new_commits)} newly active/updated days!")
            for nc in new_commits[:3]:
                print(f"  -> {nc['date']}: {nc['count']} commits (+{nc.get('new_diff', 0)} new)")
        else:
            print("[INFO] No new commit delta detected since last snapshot.")

        # 4. Plan state machine patrol timeline
        print("[DOGGO] Generating state machine patrol timeline...")
        timeline = build_timeline(grid_days, active_days, total_commits, peak_day)
        print(f"[OK] Generated {len(timeline)} timeline beats.")

        # 5. Prepare destination directory & backup existing valid GIF
        out_file.parent.mkdir(parents=True, exist_ok=True)
        (out_file.parent / ".nojekyll").touch(exist_ok=True)

        if out_file.exists() and out_file.stat().st_size > 0:
            shutil.copy2(out_file, backup_file)
            has_backup = True

        # Render to a temporary staging file first (atomic generation)
        temp_out = out_file.with_suffix(".tmp.gif")
        print(f"[DOGGO] Rendering Contribution Doggo animation to {temp_out}...")
        render_gif(
            grid_days=grid_days,
            timeline=timeline,
            total_commits=total_commits,
            peak_day=peak_day,
            username=USERNAME,
            output_path=str(temp_out),
        )

        # Atomic replacement of output file
        if temp_out.exists() and temp_out.stat().st_size > 0:
            temp_out.replace(out_file)
            if has_backup and backup_file.exists():
                backup_file.unlink()
        else:
            raise RuntimeError("Renderer produced empty or missing temporary output file.")

        # 6. Save new snapshot
        save_snapshot(grid_days, total_commits, username=USERNAME)
        print("[OK] Updated persistent contribution snapshot.")
        print(f"[OK] Successfully published {out_file} ({out_file.stat().st_size / 1024:.1f} KB).")
        return 0

    except Exception as exc:
        print(f"ERROR: Generation failed: {exc}", file=sys.stderr)
        # Safe error recovery: restore previous valid GIF if it existed
        if has_backup and backup_file.exists():
            print("[RECOVERY] Restoring previous valid GIF to prevent profile breakage...", file=sys.stderr)
            backup_file.replace(out_file)
        return 1


if __name__ == "__main__":
    sys.exit(main())
