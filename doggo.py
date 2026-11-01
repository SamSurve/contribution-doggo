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
W, H = 1200, 360
CELL, GAP = 13, 5
GX, GY, WEEKS = 82, 122, 53
STEP = CELL + GAP
BG, PANEL, BORDER = (7, 10, 22), (12, 17, 34), (45, 55, 87)
TEXT, MUTED, PURPLE = (231, 235, 250), (139, 153, 181), (170, 139, 255)
LEVELS = [(24, 31, 49), (18, 83, 65), (20, 128, 78), (39, 180, 105), (111, 239, 158)]


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fetch_contributions() -> list[dict[str, Any]]:
    if not TOKEN:
        raise RuntimeError("Missing GH_TOKEN. Add your token as the DOGGO_TOKEN Actions secret.")
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    response = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"query": query, "variables": {"login": USERNAME}},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"]))
    user = payload.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {USERNAME!r} was not found.")
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [day for week in weeks for day in week["contributionDays"]][-371:]


def intensity(count: int) -> int:
    if count <= 0: return 0
    if count <= 2: return 1
    if count <= 5: return 2
    if count <= 9: return 3
    return 4


def draw_dog(d: ImageDraw.ImageDraw, x: int, y: int, frame: int, sniff: bool = False) -> None:
    """Draw a bespoke, shaded corgi sprite facing right; x/y are its body centre."""
    phase = frame % 4
    bob = 0 if sniff else ([-2, 0, 2, 0][phase])
    y += bob
    outline = (65, 43, 47)
    coat = (226, 151, 88)
    light = (255, 218, 176)
    shadow = (177, 104, 62)

    # Ground shadow and wagging tail
    d.ellipse((x-35, y+31, x+40, y+43), fill=(4, 7, 17))
    wag = [-8, 0, 8, 0][phase]
    d.line((x-25, y-1, x-39, y-12+wag, x-47, y-5+wag), fill=outline, width=11)
    d.line((x-25, y-1, x-39, y-12+wag, x-47, y-5+wag), fill=coat, width=7)

    # Compact corgi body with cream chest and saddle shading
    d.rounded_rectangle((x-31, y-20, x+25, y+24), radius=18, fill=outline)
    d.rounded_rectangle((x-28, y-18, x+22, y+20), radius=16, fill=coat)
    d.ellipse((x-14, y-10, x+21, y+19), fill=light)
    d.rounded_rectangle((x-26, y-15, x+10, y+4), radius=10, fill=(238, 174, 111))

    # Ears behind the head
    d.polygon([(x+2,y-31),(x-2,y-55),(x+17,y-42),(x+23,y-25)], fill=outline)
    d.polygon([(x+5,y-32),(x+2,y-49),(x+15,y-40),(x+19,y-27)], fill=shadow)
    d.polygon([(x+29,y-31),(x+43,y-52),(x+45,y-22),(x+37,y-15)], fill=outline)
    d.polygon([(x+32,y-29),(x+41,y-45),(x+41,y-23),(x+36,y-19)], fill=shadow)

    # Head, cheek and muzzle; head dips towards target while sniffing
    dip = 7 if sniff else 0
    hx, hy = x+23, y-23+dip
    d.ellipse((hx-25,hy-24,hx+28,hy+25), fill=outline)
    d.ellipse((hx-22,hy-22,hx+25,hy+22), fill=coat)
    d.ellipse((hx-13,hy-3,hx+26,hy+20), fill=light)
    # Brow and eyes
    d.ellipse((hx-8,hy-7,hx-2,hy-1), fill=(35,29,34))
    d.ellipse((hx+12,hy-7,hx+18,hy-1), fill=(35,29,34))
    d.ellipse((hx+21,hy+5,hx+30,hy+12), fill=(38,31,36))
    d.arc((hx+12,hy+9,hx+27,hy+19), 5, 120, fill=(113,62,55), width=2)
    # Collar, tag and subtle highlights
    d.arc((x-20,y-16,x+23,y+13), 5, 160, fill=(104,119,255), width=6)
    d.ellipse((x+3,y+7,x+12,y+17), fill=(255,210,105), outline=(111,80,48))
    d.arc((hx-17,hy-18,hx+15,hy+12), 205, 285, fill=(255,207,154), width=2)

    # Four short legs with alternating gait; feet have cream socks
    stride = [5, -2, -5, 2][phase]
    for lx, off in ((-19, -stride), (13, stride)):
        top = y+11+off
        d.rounded_rectangle((x+lx-6,top,x+lx+6,top+18), radius=5, fill=outline)
        d.rounded_rectangle((x+lx-4,top+1,x+lx+4,top+15), radius=4, fill=shadow)
        d.rounded_rectangle((x+lx-7,top+12,x+lx+8,top+20), radius=5, fill=light)


def draw_paw(d: ImageDraw.ImageDraw, x: int, y: int, color=(176, 145, 225)):
    d.ellipse((x-4,y-1,x+4,y+6), fill=color)
    for dx, dy in ((-6,-5),(-2,-8),(3,-8),(7,-5)):
        d.ellipse((x+dx-2,y+dy-2,x+dx+2,y+dy+2), fill=color)


def build(days: list[dict[str, Any]]) -> None:
    if not days:
        raise RuntimeError("GitHub returned an empty contribution calendar.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    start = date.fromisoformat(days[0]["date"])
    grid = {date.fromisoformat(day["date"]): int(day["contributionCount"]) for day in days}
    total = sum(grid.values())
    active = sorted(((day, count) for day, count in grid.items() if count > 0), key=lambda item: item[1], reverse=True)
    target_day, target_count = active[0] if active else (start, 0)
    target_offset = (target_day-start).days
    target_col, target_row = divmod(target_offset, 7)
    target_cx = GX + target_col*STEP + CELL//2
    target_cy = GY + target_row*STEP + CELL//2

    # Dog travels along the actual calendar rows, then approaches the brightest square.
    route = []
    for i in range(30):
        col = min(WEEKS-1, round(i*(WEEKS-1)/29))
        row = 5 if i % 2 == 0 else 1
        route.append((GX+col*STEP+CELL//2, GY+row*STEP+CELL//2+22))
    approach = (max(GX+25, target_cx-35), target_cy+25)
    route.extend([
        (int(route[-1][0]+(approach[0]-route[-1][0])*t/7),
         int(route[-1][1]+(approach[1]-route[-1][1])*t/7)) for t in range(1,8)
    ])
    route.extend([approach]*10)
    route.extend([(approach[0]+i*8, approach[1]+(i%2)*2) for i in range(1,9)])

    frames = []
    for idx, (dog_x, dog_y) in enumerate(route):
        img = Image.new("RGB", (W,H), BG)
        d = ImageDraw.Draw(img)
        # Starfield specks
        for sx, sy, r in ((48,48,2),(1137,49,2),(1090,300,1),(47,303,1),(790,39,1),(930,310,2),(600,83,1)):
            d.ellipse((sx-r,sy-r,sx+r,sy+r), fill=(92,100,157))
        d.rounded_rectangle((16,14,W-16,H-14), radius=20, fill=PANEL, outline=BORDER, width=2)
        d.text((46,34),"CONTRIBUTION DOGGO",font=font(23,True),fill=TEXT)
        d.text((47,67),"Exploring the constellations of your coding year",font=font(13),fill=MUTED)
        d.text((W-255,41),f"{total:,} contributions",font=font(17,True),fill=PURPLE)
        d.text((W-255,66),f"Brightest day: {target_count} contributions",font=font(12),fill=MUTED)

        # Contribution grid: week columns, Sunday-first rows as returned by GitHub.
        for col in range(WEEKS):
            week_start = start + timedelta(days=col*7)
            if week_start.day <= 7:
                d.text((GX+col*STEP,GY-22),week_start.strftime("%b"),font=font(10),fill=MUTED)
            for row in range(7):
                day = week_start+timedelta(days=row)
                count = grid.get(day,0)
                x0,y0 = GX+col*STEP,GY+row*STEP
                d.rounded_rectangle((x0,y0,x0+CELL,y0+CELL),radius=3,fill=LEVELS[intensity(count)])

        # Gold locator around the high-activity square
        if target_count:
            pulse = 3 + (idx % 4)
            d.rounded_rectangle((target_cx-pulse,target_cy-pulse,target_cx+CELL+pulse,target_cy+CELL+pulse),
                                radius=5,outline=(255,207,125),width=2)
        sniffing = len(route)-18 <= idx < len(route)-8
        if sniffing:
            # Nose is on the right; dog stands just left of the highlighted contribution.
            draw_paw(d,dog_x-42,dog_y+34)
            draw_paw(d,dog_x-63,dog_y+39)
            d.text((dog_x+28,dog_y-68),"sniff…",font=font(13,True),fill=(255,211,145))
            d.arc((dog_x+22,dog_y-57,dog_x+49,dog_y-29),195,320,fill=(255,211,145),width=2)
        draw_dog(d,dog_x,dog_y,idx,sniff=sniffing)
        d.text((46,H-43),"REAL GITHUB CONTRIBUTIONS  •  UPDATED AUTOMATICALLY",font=font(10),fill=MUTED)
        frames.append(img.convert("P",palette=Image.Palette.ADAPTIVE,colors=160))

    frames[0].save(OUT,save_all=True,append_images=frames[1:],duration=70,loop=0,optimize=True,disposal=2)
    print(f"Generated {OUT} for @{USERNAME}: {total} contributions; brightest day={target_count}.")


if __name__ == "__main__":
    try:
        build(fetch_contributions())
    except Exception as exc:
        print(f"ERROR: {exc}",file=sys.stderr)
        raise
