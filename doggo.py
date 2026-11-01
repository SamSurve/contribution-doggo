#!/usr/bin/env python3
"""
Contribution Doggo
A premium animated pixel-art corgi companion living inside your GitHub contribution calendar.
"""
from __future__ import annotations

import io
import json
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
from src.snapshot import (
    DIST_SNAPSHOT,
    SNAPSHOT_FILE,
    detect_new_contributions,
    load_previous_snapshot,
    save_snapshot,
    stage_snapshot_data,
)

USERNAME = os.getenv("GITHUB_USERNAME", "SamSurve")
TOKEN = os.getenv("DOGGO_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "dist/contribution-doggo.gif")


def main() -> int:
    # --- File Paths Configuration ---
    out_file = Path(OUTPUT_PATH)
    backup_gif = out_file.with_suffix(".gif.bak")
    stage_gif = out_file.with_suffix(".tmp.gif")

    snapshot_path_env = os.getenv("SNAPSHOT_PATH")
    data_snap = Path(snapshot_path_env) if snapshot_path_env else SNAPSHOT_FILE
    backup_data = data_snap.with_suffix(".json.bak")
    stage_data = data_snap.with_suffix(".tmp")

    dist_snap_env = os.getenv("DIST_SNAPSHOT_PATH")
    dist_snap = Path(dist_snap_env) if dist_snap_env else DIST_SNAPSHOT
    backup_dist = dist_snap.with_suffix(".json.bak")
    stage_dist = dist_snap.with_suffix(".tmp")

    # --- Transaction State Tracking ---
    # Initialized BEFORE try block to guarantee safe early error handling without UnboundLocalError
    has_gif_backup = False
    has_data_backup = False
    has_dist_backup = False

    gif_promoted = False
    data_promoted = False
    dist_promoted = False
    has_new_snapshot_to_promote = False
    should_mirror_dist = (not snapshot_path_env and not dist_snap_env) or (dist_snap_env is not None)

    try:
        # 1. Back up all existing valid production artifacts
        out_file.parent.mkdir(parents=True, exist_ok=True)
        (out_file.parent / ".nojekyll").touch(exist_ok=True)

        if out_file.is_file() and out_file.stat().st_size > 0:
            shutil.copy2(out_file, backup_gif)
            has_gif_backup = True

        if data_snap.is_file() and data_snap.stat().st_size > 0:
            data_snap.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(data_snap, backup_data)
            has_data_backup = True

        if dist_snap.is_file() and dist_snap.stat().st_size > 0:
            dist_snap.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dist_snap, backup_dist)
            has_dist_backup = True

        # 2. Load snapshot baseline & fetch live contribution calendar
        prev_snapshot = load_previous_snapshot(custom_path=data_snap if snapshot_path_env else None)
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

        # 5. Generate the new GIF into a temporary staging file
        print(f"[DOGGO] Rendering Contribution Doggo animation to {stage_gif}...")
        render_gif(
            grid_days=grid_days,
            timeline=timeline,
            total_commits=total_contributions,
            peak_day=peak_day,
            username=USERNAME,
            output_path=str(stage_gif),
        )

        # 6. Validate the staged GIF
        if not stage_gif.is_file() or stage_gif.stat().st_size == 0:
            raise RuntimeError("Renderer produced empty or missing temporary output file.")

        from PIL import Image as PILImage
        with PILImage.open(stage_gif) as test_img:
            if getattr(test_img, "format", "") != "GIF":
                raise RuntimeError(f"Generated staging file is not a valid GIF format: {getattr(test_img, 'format', None)}")
            n_frames = getattr(test_img, "n_frames", 1)
            if n_frames < 10:
                raise RuntimeError(
                    f"Generated GIF failed validation: insufficient frames ({n_frames} < 10)."
                )

        # 7. Generate and stage the new snapshot without overwriting current valid snapshot
        if commit_tracking_available:
            snapshot_dict = stage_snapshot_data(
                grid_days=grid_days,
                total_contributions=total_contributions,
                username=USERNAME,
                commit_tracking_available=True,
            )
            # Stage data snapshot
            stage_data.parent.mkdir(parents=True, exist_ok=True)
            with open(stage_data, "w", encoding="utf-8") as f:
                json.dump(snapshot_dict, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            with open(stage_data, "r", encoding="utf-8") as f:
                if not json.load(f):
                    raise RuntimeError("Staged data snapshot file is empty or corrupted.")

            # Stage dist snapshot (when running in primary production or explicitly configured)
            if should_mirror_dist:
                stage_dist.parent.mkdir(parents=True, exist_ok=True)
                with open(stage_dist, "w", encoding="utf-8") as f:
                    json.dump(snapshot_dict, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                with open(stage_dist, "r", encoding="utf-8") as f:
                    if not json.load(f):
                        raise RuntimeError("Staged dist snapshot file is empty or corrupted.")

            has_new_snapshot_to_promote = True
        else:
            print("[SNAPSHOT] Preserved existing snapshot without advancement (commit tracking was unavailable).")

        # 8. Promote the new GIF and both new snapshot files atomically
        os.replace(stage_gif, out_file)
        gif_promoted = True

        if has_new_snapshot_to_promote:
            os.replace(stage_data, data_snap)
            data_promoted = True

            if should_mirror_dist and stage_dist.exists():
                os.replace(stage_dist, dist_snap)
                dist_promoted = True

        # 9. Verify all promoted files
        if not out_file.is_file() or out_file.stat().st_size == 0:
            raise RuntimeError("Promoted GIF file is missing or empty.")

        if has_new_snapshot_to_promote:
            if not data_snap.is_file() or data_snap.stat().st_size == 0:
                raise RuntimeError("Promoted data snapshot file is missing or empty.")
            if should_mirror_dist and (not dist_snap.is_file() or dist_snap.stat().st_size == 0):
                raise RuntimeError("Promoted dist snapshot file is missing or empty.")

        # 10. Only after ALL operations succeed, delete the backups
        if has_gif_backup and backup_gif.exists():
            backup_gif.unlink()
        if has_data_backup and backup_data.exists():
            backup_data.unlink()
        if has_dist_backup and backup_dist.exists():
            backup_dist.unlink()

        if has_new_snapshot_to_promote:
            print("[OK] Updated persistent contribution snapshots (data/ and dist/).")
        print(f"[OK] Successfully published {out_file} ({out_file.stat().st_size / 1024:.1f} KB).")
        return 0

    except Exception as exc:
        print(f"ERROR: Generation failed: {exc}", file=sys.stderr)
        print("[ROLLBACK] Initiating complete transactional rollback of all production artifacts...", file=sys.stderr)

        # 1. Rollback GIF
        if has_gif_backup and backup_gif.exists():
            try:
                shutil.copy2(backup_gif, out_file)
                backup_gif.unlink()
                print(f"[ROLLBACK] Restored previous valid GIF to {out_file}.", file=sys.stderr)
            except Exception as e:
                print(f"[ROLLBACK-WARN] Failed to restore GIF backup: {e}", file=sys.stderr)
        elif not has_gif_backup and gif_promoted and out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass

        # 2. Rollback Data Snapshot
        if has_data_backup and backup_data.exists():
            try:
                shutil.copy2(backup_data, data_snap)
                backup_data.unlink()
                print(f"[ROLLBACK] Restored previous data snapshot to {data_snap}.", file=sys.stderr)
            except Exception as e:
                print(f"[ROLLBACK-WARN] Failed to restore data snapshot backup: {e}", file=sys.stderr)
        elif not has_data_backup and data_promoted and data_snap.exists():
            try:
                data_snap.unlink()
            except Exception:
                pass

        # 3. Rollback Dist Snapshot
        if has_dist_backup and backup_dist.exists():
            try:
                shutil.copy2(backup_dist, dist_snap)
                backup_dist.unlink()
                print(f"[ROLLBACK] Restored previous dist snapshot to {dist_snap}.", file=sys.stderr)
            except Exception as e:
                print(f"[ROLLBACK-WARN] Failed to restore dist snapshot backup: {e}", file=sys.stderr)
        elif not has_dist_backup and dist_promoted and dist_snap.exists():
            try:
                dist_snap.unlink()
            except Exception:
                pass

        # 4. Clean up any lingering temporary / staging files
        for tmp_file in (stage_gif, stage_data, stage_dist, backup_gif, backup_data, backup_dist):
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

        return 1


if __name__ == "__main__":
    sys.exit(main())
