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
