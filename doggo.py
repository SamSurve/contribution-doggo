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
            tot_c = prev_snapshot.get("total_contributions", 0)
            tot_cm = prev_snapshot.get("total_commits", 0)
            is_legacy = "daily_commit_counts" not in prev_snapshot
            if is_legacy:
                print(f"[SNAPSHOT] Loaded legacy snapshot ({tot_c} contributions). Will perform baseline migration.")
            else:
                print(f"[SNAPSHOT] Loaded previous snapshot ({tot_c} contributions, {tot_cm} commits).")
        else:
            print("[SNAPSHOT] First-run baseline: initializing snapshot without previous history.")

        # 2. Fetch live contribution calendar (protects against synthetic mock overwrite)
        print(f"[DOGGO] Fetching GitHub contributions for @{USERNAME}...")
        contrib_data = fetch_contributions(
            username=USERNAME, token=TOKEN, allow_synthetic=False
        )
        grid_days, active_days, total_contributions, peak_day = contrib_data
        commit_tracking_available = (
            getattr(contrib_data, "commit_tracking_available", True)
            and not any(item.get("commit_count") is None for item in grid_days.values())
        )
        print(f"[OK] Fetched {len(grid_days)} days ({len(active_days)} active). Total contributions: {total_contributions}.")
        if peak_day:
            print(f"[OK] Peak day: {peak_day['date']} with {peak_day['count']} contributions.")

        # 3. Detect newly added commits since previous snapshot (commit-specific)
        if commit_tracking_available:
            new_commits = detect_new_contributions(
                grid_days, prev_snapshot, commit_tracking_available=True
            )
            if new_commits:
                print(f"[NEW COMMITS] Detected {len(new_commits)} newly active/updated commit dates!")
                for nc in new_commits[:4]:
                    print(f"  -> {nc['date']}: {nc.get('commit_count', 0)} commits (+{nc.get('new_commits_diff', 0)} new)")
            else:
                print("[INFO] No new commit delta detected since last snapshot.")
        else:
            new_commits = []
            print("[WARN] Commit tracking is unavailable (public web fallback). Skipping commit detection.")

        # 4. Plan state machine patrol timeline with priority routing
        print("[DOGGO] Generating state machine patrol timeline...")
        timeline = build_timeline(grid_days, active_days, total_contributions, peak_day)
        print(f"[OK] Generated {len(timeline)} timeline beats.")

        # 5. Transaction step 1: Preserve the old GIF backup
        out_file.parent.mkdir(parents=True, exist_ok=True)
        (out_file.parent / ".nojekyll").touch(exist_ok=True)

        if out_file.exists() and out_file.stat().st_size > 0:
            shutil.copy2(out_file, backup_file)
            has_backup = True

        # Transaction step 2: Generate and validate the new GIF to a staging file
        temp_out = out_file.with_suffix(".tmp.gif")
        print(f"[DOGGO] Rendering Contribution Doggo animation to {temp_out}...")
        render_gif(
            grid_days=grid_days,
            timeline=timeline,
            total_commits=total_contributions,
            peak_day=peak_day,
            username=USERNAME,
            output_path=str(temp_out),
        )

        # Validate that the generated staging GIF exists and is non-empty
        if not temp_out.exists() or temp_out.stat().st_size == 0:
            raise RuntimeError("Renderer produced empty or missing temporary output file.")

        # Validate that the generated file is a valid animated GIF
        from PIL import Image as PILImage
        with PILImage.open(temp_out) as test_img:
            if getattr(test_img, "n_frames", 1) < 10:
                raise RuntimeError(
                    f"Generated GIF failed validation: insufficient frames ({getattr(test_img, 'n_frames', 1)})."
                )

        # Transaction step 3: Save the snapshot successfully BEFORE committing/deleting backup
        if commit_tracking_available:
            save_snapshot(
                grid_days, total_contributions, username=USERNAME, commit_tracking_available=True
            )
            print("[OK] Updated persistent contribution snapshot.")
        else:
            print("[SNAPSHOT] Preserved existing snapshot without advancement (commit tracking was unavailable).")

        # Promote validated temp GIF to out_file
        temp_out.replace(out_file)

        # Transaction step 4: Only after BOTH operations succeed, delete the old backup
        if has_backup and backup_file.exists():
            backup_file.unlink()

        print(f"[OK] Successfully published {out_file} ({out_file.stat().st_size / 1024:.1f} KB).")
        return 0

    except Exception as exc:
        print(f"ERROR: Generation failed: {exc}", file=sys.stderr)
        # Transaction step 5: If either operation fails, restore previous GIF and preserve previous valid snapshot
        if has_backup and backup_file.exists():
            print("[RECOVERY] Restoring previous valid GIF to prevent profile breakage...", file=sys.stderr)
            backup_file.replace(out_file)
        if temp_out.exists():
            try:
                temp_out.unlink()
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
