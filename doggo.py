#!/usr/bin/env python3
"""
Contribution Doggo
A premium animated pixel-art corgi companion living inside your GitHub contribution calendar.
"""
from __future__ import annotations

import io
import os
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

USERNAME = os.getenv("GITHUB_USERNAME", "SamSurve")
TOKEN = os.getenv("DOGGO_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "dist/contribution-doggo.gif")


def main() -> int:
    try:
        print(f"[DOGGO] Fetching GitHub contributions for @{USERNAME}...")
        grid_days, active_days, total_commits, peak_day = fetch_contributions(
            username=USERNAME, token=TOKEN
        )
        print(f"[OK] Fetched {len(grid_days)} days ({len(active_days)} active). Total contributions: {total_commits}.")
        if peak_day:
            print(f"[OK] Peak day: {peak_day['date']} with {peak_day['count']} commits.")

        print("[DOGGO] Generating state machine patrol timeline...")
        timeline = build_timeline(grid_days, active_days, total_commits, peak_day)
        print(f"[OK] Generated {len(timeline)} animation frames.")

        print(f"[DOGGO] Rendering Contribution Doggo animation to {OUTPUT_PATH}...")
        out_p = Path(OUTPUT_PATH)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        (out_p.parent / ".nojekyll").touch(exist_ok=True)
        render_gif(
            grid_days=grid_days,
            timeline=timeline,
            total_commits=total_commits,
            peak_day=peak_day,
            username=USERNAME,
            output_path=OUTPUT_PATH,
        )
        print("[OK] All done! Contribution Doggo is ready to explore.")
        return 0
    except Exception as exc:
        print(f"ERROR: Failed to generate Contribution Doggo: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
