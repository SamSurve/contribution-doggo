from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

USERNAME = os.getenv("GITHUB_USERNAME", "SamSurve")
TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
OUT = Path("dist/contribution-doggo.gif")
WIDTH, HEIGHT = 1200, 330
CELL, GAP = 13, 5
GRID_X, GRID_Y = 82, 112
WEEKS = 53
BG, PANEL, BORDER = (9, 12, 24), (14, 19, 36), (43, 54, 82)
TEXT, MUTED, ACCENT = (225, 232, 248), (139, 153, 181), (151, 120, 255)
GREEN = [(24, 32, 48), (14, 91, 67), (20, 137, 82), (45, 190, 112), (110, 239, 159)]


def font(size: int, bold: bool = False):
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def fetch_contributions() -> list[dict[str, Any]]:
    if not TOKEN:
        raise RuntimeError("Missing GH_TOKEN. Add a PAT as the DOGGO_TOKEN repository secret.")
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount color } }
          }
        }
      }
    }
    """
    res = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"},
        json={"query": query, "variables": {"login": USERNAME}},
        timeout=30,
    )
    res.raise_for_status()
    payload = res.json()
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"]))
    user = payload.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {USERNAME!r} was not found.")
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [day for week in weeks for day in week["contributionDays"]][-371:]


def level(count: int) -> int:
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 9:
        return 3
    return 4


def draw_dog(draw: ImageDraw.ImageDraw, x: int, y: int, frame: int, sniff: bool = False) -> None:
    bob = 0 if sniff else (-3 if frame % 4 in (1, 2) else 0)
    y += bob
    draw.ellipse((x - 35, y + 42, x + 48, y + 53), fill=(5, 8, 16))
    draw.line((x - 24, y + 5, x - 38, y - 7, x - 45, y - 2), fill=(222, 151, 91), width=9)
    draw.rounded_rectangle((x - 27, y - 5, x + 28, y + 31), radius=15, fill=(220, 145, 82))
    draw.rounded_rectangle((x - 20, y + 10, x + 18, y + 28), radius=9, fill=(247, 224, 190))
    draw.polygon([(x - 22, y - 23), (x - 27, y - 49), (x - 8, y - 31)], fill=(184, 105, 62))
    draw.polygon([(x + 12, y - 31), (x + 30, y - 49), (x + 28, y - 20)], fill=(184, 105, 62))
    hy = y - 24 + (5 if sniff else 0)
    draw.ellipse((x - 25, hy - 17, x + 29, hy + 29), fill=(231, 165, 101))
    draw.ellipse((x - 17, hy + 7, x + 21, hy + 29), fill=(250, 228, 197))
    draw.ellipse((x - 10, hy + 1, x - 5, hy + 7), fill=(31, 25, 28))
    draw.ellipse((x + 11, hy + 1, x + 16, hy + 7), fill=(31, 25, 28))
    draw.ellipse((x + 1, hy + 15, x + 9, hy + 21), fill=(42, 31, 34))
    draw.arc((x - 2, hy + 18, x + 12, hy + 29), 0, 130, fill=(91, 48, 45), width=2)
    draw.arc((x - 19, y - 11, x + 20, y + 15), 10, 165, fill=(95, 116, 255), width=6)
    draw.ellipse((x + 1, y + 9, x + 9, y + 17), fill=(255, 211, 106))
    stride = 5 if frame % 2 else -3
    for lx, offset in ((-17, stride), (15, -stride)):
        draw.rounded_rectangle((x + lx - 5, y + 22 + offset, x + lx + 5, y + 43 + offset), radius=4, fill=(207, 132, 74))
        draw.rounded_rectangle((x + lx - 7, y + 37 + offset, x + lx + 7, y + 45 + offset), radius=4, fill=(247, 222, 190))


def build(days: list[dict[str, Any]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    start = date.fromisoformat(days[0]["date"])
    grid = {date.fromisoformat(d["date"]): int(d["contributionCount"]) for d in days}
    total = sum(grid.values())
    active = [(day, count) for day, count in grid.items() if count > 0]
    sniff_day, sniff_count = max(active, key=lambda item: item[1]) if active else (start, 0)
    sniff_col = (sniff_day - start).days // 7
    sniff_row = (sniff_day - start).days % 7
    sniff_x = GRID_X + sniff_col * (CELL + GAP) + CELL // 2
    sniff_y = GRID_Y + sniff_row * (CELL + GAP) + CELL // 2
    dog_start = GRID_X + 8
    target_x = max(dog_start + 45, min(WIDTH - 75, sniff_x + 30))
    positions = [int(dog_start + (target_x - dog_start) * i / 14) for i in range(15)]
    positions += [target_x] * 8
    positions += [int(target_x + (WIDTH - 110 - target_x) * i / 12) for i in range(1, 13)]
    frames = []

    for idx, dog_x in enumerate(positions):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        d = ImageDraw.Draw(img)
        for sx, sy, radius in ((50, 44, 2), (1120, 45, 2), (1090, 275, 1), (42, 280, 1), (790, 35, 1), (930, 285, 2)):
            d.ellipse((sx-radius, sy-radius, sx+radius, sy+radius), fill=(86, 94, 143))
        d.rounded_rectangle((18, 14, WIDTH-18, HEIGHT-14), radius=20, fill=PANEL, outline=BORDER, width=2)
        d.text((48, 35), "CONTRIBUTION DOGGO", font=font(23, True), fill=TEXT)
        d.text((49, 68), "A little companion exploring your coding year", font=font(13), fill=MUTED)
        d.text((WIDTH-255, 43), f"{total:,} contributions", font=font(17, True), fill=ACCENT)
        d.text((WIDTH-255, 67), f"Peak day: {sniff_count} contributions", font=font(13), fill=MUTED)

        for row, label in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
            d.text((39, GRID_Y + row*(CELL+GAP) + 1), label, font=font(11), fill=MUTED)
        for col in range(WEEKS):
            week_start = start + timedelta(days=col*7)
            if week_start.day <= 7:
                d.text((GRID_X + col*(CELL+GAP), GRID_Y-22), week_start.strftime("%b"), font=font(11), fill=MUTED)
            for row in range(7):
                day = week_start + timedelta(days=row)
                count = grid.get(day, 0)
                x0, y0 = GRID_X + col*(CELL+GAP), GRID_Y + row*(CELL+GAP)
                d.rounded_rectangle((x0, y0, x0+CELL, y0+CELL), radius=3, fill=GREEN[level(count)])

        if sniff_count:
            d.rounded_rectangle((sniff_x-5, sniff_y-5, sniff_x+CELL+5, sniff_y+CELL+5), radius=5, outline=(255, 210, 128), width=2)
        sniffing = 15 <= idx < 23
        dog_y = max(202, min(245, sniff_y + 58)) if sniffing else 220
        if sniffing:
            for p in range(3):
                px, py = dog_x - 44 - p*19, dog_y + 29 + (p % 2)*6
                d.ellipse((px, py, px+5, py+5), fill=(183, 140, 219))
                for toe in range(3):
                    d.ellipse((px+toe*4-2, py-5, px+toe*4+1, py-2), fill=(183, 140, 219))
            d.text((dog_x+34, dog_y-61), "sniff…", font=font(14, True), fill=(255, 211, 139))
            d.arc((dog_x+20, dog_y-53, dog_x+45, dog_y-28), 200, 330, fill=(255, 211, 139), width=2)
        draw_dog(d, dog_x, dog_y, idx, sniff=sniffing)
        d.text((48, HEIGHT-42), "REAL CONTRIBUTION DATA  •  GENERATED AUTOMATICALLY", font=font(11), fill=MUTED)
        frames.append(img.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))

    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=75, loop=0, optimize=True, disposal=2)
    print(f"Generated {OUT} ({OUT.stat().st_size:,} bytes) for @{USERNAME}; total={total}, peak={sniff_count}.")


if __name__ == "__main__":
    try:
        build(fetch_contributions())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
