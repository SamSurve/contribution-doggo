# Contribution Doggo — Architecture & Design

## Overview

Contribution Doggo is an autonomous, pixel-art animated companion that physically lives inside a GitHub contribution calendar. Designed for `@SamSurve`, it brings GitHub profiles to life with game-quality pixel animation, dynamic target selection, and interactive grid navigation.

## Architecture

```
e:\DOGGO/
├── .github/workflows/
│   └── generate-doggo.yml   # Scheduled daily regeneration & publishing
├── src/
│   ├── __init__.py
│   ├── corgi.py             # Bespoke pixel-art corgi sprite generator (32x22 RGBA)
│   ├── fetcher.py           # GitHub GraphQL + Web fallback contribution fetcher
│   ├── planner.py           # Multi-target selection, coordinate mapping & state machine
│   └── renderer.py          # 53x7 dark-mode grid renderer & optimized GIF generator
├── tests/
│   ├── test_corgi.py        # Sprite dimension, content, and flip tests
│   ├── test_fetcher.py      # Future contribution simulation & fallback tests
│   └── test_planner.py      # Grid boundary, state transitions & loop continuity tests
├── doggo.py                 # Main CLI pipeline
└── requirements.txt         # Pillow, requests, pytest
```

## Features

- **Pixel-Art Corgi**: Original 32x22 sprite with warm orange coat, white chest ruff, perky fox ears, button nose, and blue collar with gold tag.
- **Natural Animation States**:
  - `idle`: Calm breathing and alert posture
  - `run`: 4-frame galloping trotting cycle with leg alternation and body bob
  - `look_around`: Ears perked, looking at viewer
  - `sniff`: Body crouch, head dipping towards active contribution square, floating scent sparkles
  - `paw_touch`: Front paw reaching out and tapping the square
  - `happy`: Excited tail wag and celebration
- **Grid Alignment**: Paws are aligned directly to contribution rows, nose touches target squares.
- **Pawprint Stamping**: Visited active squares are permanently stamped with glowing pixel-art pawprints.
- **Dynamic Exploration**: Visited targets are dynamically selected across different dates and weekday rows.
- **GitHub Dark Mode Aesthetic**: Authentic colors (`#0d1117`, `#11161e`, `#30363d`), distinct empty squares, month and weekday labels, and real-time status ticker with glowing LED indicator.
- **Future-Proof**: Supports rolling calendar dates, year transitions, and new contributions automatically.

## Security

Authentication uses the `DOGGO_TOKEN` Actions secret for GraphQL queries. Tokens and secrets are never committed or exposed.

## v2 Visual Redesign (branch `claude/visual-redesign`)
- **Sprites** (`src/corgi.py`): hand-authored ASCII pixel parts (body, head, front-face head, 4 ear poses) composed per frame with auto-outline. 8 states: idle(4) walk(6) run(6) look_around(4) sniff(4) paw_touch(4) happy(4) rest(4). Same 32x22 RGBA API; renderer scales 2x nearest-neighbour.
- **Story** (`expand_timeline` in `src/renderer.py`): rest -> wake -> walk/run with ease-in/out -> look around -> sniff -> paw lift/touch -> stamp -> happy wag -> patrol -> settle to rest. Planner untouched; the renderer re-times its output.
- **Grid**: same 53x7 geometry (GX/GY/CELL/STEP unchanged). Flat rounded cells, quieter labels, subtle gold tint + hairline ring on target, three rising scent dots, stamp ring on pawprint.
- **Loop seam**: first and last frames are pixel-identical (paws fade during final rest).
- **Output**: one shared palette for all frames (no flicker, no dither), per-frame durations, bundled Pillow font (no system fonts).
