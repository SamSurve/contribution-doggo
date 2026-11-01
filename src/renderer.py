"""
Frame renderer and GIF generator for Contribution Doggo.
"""
from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.corgi import render_corgi_frame

# Layout & Dimensions
W, H = 1100, 340
GX, GY = 110, 122
CELL, GAP = 12, 4
STEP = CELL + GAP
WEEKS = 53

# Dark Theme GitHub Palette
BG = (13, 17, 23)           # #0d1117 GitHub Background
PANEL = (17, 22, 30)        # #11161e Dark card surface
BORDER = (48, 54, 61)       # #30363d GitHub border
TEXT = (240, 246, 252)      # Primary text
MUTED = (139, 148, 158)     # Secondary text
ACCENT = (88, 166, 255)     # GitHub Blue
GOLD = (245, 158, 11)       # Warm Gold Accent

# Official GitHub dark mode contribution greens with distinct empty level 0
GREEN_LEVELS = [
    (27, 34, 45),           # Level 0 (visible dark cell)
    (14, 68, 41),           # Level 1
    (0, 109, 50),           # Level 2
    (38, 166, 65),          # Level 3
    (57, 211, 83),          # Level 4
]
EMPTY_BORDER = (38, 46, 60)
PAW_COLOR = (255, 235, 160, 245)


def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Loads system font with fallback to default."""
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_pawprint(d: ImageDraw.ImageDraw, cx: int, cy: int, color=PAW_COLOR) -> None:
    """Draws a crisp 5x5 pixel-art pawprint centered at (cx, cy)."""
    d.rectangle([cx-2, cy, cx+1, cy+2], fill=color)
    d.point((cx-3, cy-2), fill=color)
    d.point((cx-1, cy-3), fill=color)
    d.point((cx+1, cy-3), fill=color)
    d.point((cx+3, cy-2), fill=color)


def draw_mini_corgi_badge(d: ImageDraw.ImageDraw, bx: int, by: int) -> None:
    """Draws a cute 18x18 pixel art corgi avatar for the header."""
    d.polygon([(bx+1, by+4), (bx+3, by), (bx+6, by+4)], fill=(224, 122, 34), outline=(48, 28, 16))
    d.polygon([(bx+10, by+4), (bx+13, by), (bx+15, by+4)], fill=(224, 122, 34), outline=(48, 28, 16))
    d.point((bx+3, by+2), fill=(244, 114, 158))
    d.point((bx+13, by+2), fill=(244, 114, 158))
    d.rounded_rectangle([bx+2, by+4, bx+14, by+14], radius=3, fill=(224, 122, 34), outline=(48, 28, 16))
    d.rectangle([bx+6, by+5, bx+10, by+14], fill=(255, 255, 255))
    d.point((bx+4, by+7), fill=(18, 18, 24))
    d.point((bx+12, by+7), fill=(18, 18, 24))
    d.rectangle([bx+6, by+10, bx+10, by+13], fill=(255, 228, 196), outline=(48, 28, 16))
    d.rectangle([bx+7, by+10, bx+9, by+11], fill=(18, 18, 24))


def render_gif(
    grid_days: Dict[Tuple[int, int], Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    total_commits: int,
    peak_day: Dict[str, Any] | None,
    username: str = "SamSurve",
    output_path: str = "dist/contribution-doggo.gif",
) -> None:
    """
    Renders the complete animated GIF with smooth timing and optimized palette.
    """
    t0 = time.time()
    f_title = get_font(16, bold=True)
    f_sub = get_font(12, bold=False)
    f_pill_title = get_font(13, bold=True)
    f_pill_sub = get_font(11, bold=False)
    f_label = get_font(10, bold=False)
    f_status = get_font(11, bold=True)

    # 1. Pre-render static base card
    base_card = Image.new("RGBA", (W, H), BG)
    d_base = ImageDraw.Draw(base_card)
    d_base.rounded_rectangle([16, 14, W-16, H-14], radius=12, fill=PANEL, outline=BORDER, width=1)

    # Header
    draw_mini_corgi_badge(d_base, 42, 28)
    d_base.text((66, 28), f"{username} / Contribution Doggo", fill=TEXT, font=f_title)
    d_base.text((66, 52), f"Autonomous Profile Companion · {total_commits} contributions in the last year", fill=MUTED, font=f_sub)

    # Right stats pill
    pill_w = 280
    pill_x = W - 42 - pill_w
    d_base.rounded_rectangle([pill_x, 26, pill_x + pill_w, 72], radius=8, fill=(24, 30, 42), outline=BORDER, width=1)
    d_base.text((pill_x + 14, 33), f"{total_commits} Contributions Patrol", fill=ACCENT, font=f_pill_title)
    peak_str = f"Brightest: {peak_day['count']} commits on {peak_day['date']}" if peak_day else "Ready for new commits"
    d_base.text((pill_x + 14, 51), peak_str, fill=GOLD, font=f_pill_sub)

    # Month Labels
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    last_month = None
    for col in range(WEEKS):
        day_info = grid_days.get((col, 0))
        if day_info:
            d_obj = date.fromisoformat(day_info["date"])
            if d_obj.month != last_month:
                last_month = d_obj.month
                d_base.text((GX + col * STEP, GY - 18), month_names[d_obj.month - 1], fill=MUTED, font=f_label)

    # Weekday labels
    d_base.text((GX - 32, GY + 1 * STEP + 1), "Mon", fill=MUTED, font=f_label)
    d_base.text((GX - 32, GY + 3 * STEP + 1), "Wed", fill=MUTED, font=f_label)
    d_base.text((GX - 32, GY + 5 * STEP + 1), "Fri", fill=MUTED, font=f_label)

    # Legend in bottom right
    leg_x = W - 180
    leg_y = H - 38
    d_base.text((leg_x - 30, leg_y), "Less", fill=MUTED, font=f_label)
    for i, colr in enumerate(GREEN_LEVELS):
        d_base.rounded_rectangle([leg_x + i * 14, leg_y, leg_x + i * 14 + 10, leg_y + 10], radius=2, fill=colr)
    d_base.text((leg_x + 5 * 14 + 4, leg_y), "More", fill=MUTED, font=f_label)

    # Pre-render sprite cache for speed
    sprite_cache = {}
    for st in ["idle", "run", "sniff", "paw_touch", "happy", "look_around"]:
        for f in range(4):
            for fl in [False, True]:
                sprite_cache[(st, f, fl)] = render_corgi_frame(st, f, facing_left=fl)

    # 2. Render each timeline frame
    frames: List[Image.Image] = []
    for idx, item in enumerate(timeline):
        frame_img = base_card.copy()
        d = ImageDraw.Draw(frame_img)

        # Draw Grid Squares
        for col in range(WEEKS):
            for row in range(7):
                cell_info = grid_days.get((col, row))
                lvl = cell_info["level"] if cell_info else 0
                x0 = GX + col * STEP
                y0 = GY + row * STEP
                if lvl == 0:
                    d.rounded_rectangle([x0, y0, x0 + CELL, y0 + CELL], radius=2, fill=GREEN_LEVELS[0], outline=EMPTY_BORDER, width=1)
                else:
                    d.rounded_rectangle([x0, y0, x0 + CELL, y0 + CELL], radius=2, fill=GREEN_LEVELS[lvl])

        # Draw Visited Pawprints on visited cells
        for (p_col, p_row) in item["paws"]:
            px0 = GX + p_col * STEP + CELL // 2
            py0 = GY + p_row * STEP + CELL // 2
            draw_pawprint(d, px0, py0, PAW_COLOR)

        # Target locator & sniff sparkle
        if item["target"] and item["sparkle"]:
            t_col = item["target"]["col"]
            t_row = item["target"]["row"]
            tx0 = GX + t_col * STEP
            ty0 = GY + t_row * STEP

            pulse = 1 + (idx % 3)
            d.rounded_rectangle([tx0 - pulse, ty0 - pulse, tx0 + CELL + pulse, ty0 + CELL + pulse],
                                radius=4, outline=GOLD, width=2)

            sniff_spark_x = tx0 + CELL // 2
            sniff_spark_y = ty0 - 10 - (idx % 3)
            d.text((sniff_spark_x - 12, sniff_spark_y), "✦ sniff", fill=GOLD, font=f_label)

        # Paste Dog Sprite
        spr = sprite_cache.get((item["state"], item["frame"], item["facing_left"]))
        if spr:
            frame_img.paste(spr, (item["x"], item["y"]), spr)

        # Status Ticker (bottom left)
        dot_color = (63, 185, 80) if (idx % 4 < 2) else (86, 211, 100)
        d.ellipse([42, H - 36, 50, H - 28], fill=dot_color)
        d.text((58, H - 38), item["status"], fill=TEXT, font=f_status)

        # Adaptive palette conversion
        p_frame = frame_img.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=96)
        frames.append(p_frame)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out_file,
        save_all=True,
        append_images=frames[1:],
        duration=75,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Successfully generated {out_file} ({len(frames)} frames) in {time.time()-t0:.2f}s! Size: {out_file.stat().st_size / 1024:.1f} KB")
