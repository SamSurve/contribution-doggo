"""
Frame renderer and GIF generator for Contribution Doggo (v2 visual redesign).

Public API unchanged: render_gif(grid_days, timeline, total_commits, peak_day, username, output_path).
The planner's timeline is *expanded* here into a smoother, story-driven beat list
(rest -> wake -> walk/run with easing -> sniff -> paw -> stamp -> celebrate -> rest)
without changing planner data structures.
"""
from __future__ import annotations

import math
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.corgi import BASELINE_Y, CENTER_X, PALETTE as SPRITE_PALETTE, get_anchors, render_corgi_frame

# Layout & Dimensions (must stay in sync with planner constants)
W, H = 1100, 340
GX, GY = 110, 122
CELL, GAP = 12, 4
STEP = CELL + GAP
WEEKS = 53
SCALE = 1.5                     # sprite upscale (nearest-neighbour)
SPR_W, SPR_H = round(32 * SCALE), round(22 * SCALE)

# Palette
BG = (8, 11, 16)
PANEL = (13, 17, 23)
BORDER = (33, 40, 50)
TEXT = (230, 237, 243)
MUTED = (125, 133, 144)
FAINT = (72, 80, 92)
GOLD = (240, 190, 90)
LEVELS = [(22, 27, 34), (14, 68, 41), (0, 109, 50), (38, 166, 65), (57, 211, 83)]
GREEN_LEVELS = LEVELS           # backwards-compatible alias
PAW_COLOR = (255, 236, 190, 235)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Pillow's bundled FreeType font: identical on every platform, no system fonts needed."""
    return ImageFont.load_default(size=size)


def cell_origin(col: int, row: int) -> Tuple[int, int]:
    return GX + col * STEP, GY + row * STEP


def draw_pawprint(d: ImageDraw.ImageDraw, cx: int, cy: int, color=PAW_COLOR) -> None:
    """Crisp pawprint centred at (cx, cy); spans cx-3..cx+3 / cy-3..cy+2 (fits a 12px cell)."""
    d.rectangle([cx - 2, cy, cx + 1, cy + 2], fill=color)
    for px, py in ((cx - 3, cy - 2), (cx + 3, cy - 2)):
        d.rectangle([px, py, px, py + 1], fill=color)
    for px in (cx - 1, cx + 1):
        d.rectangle([px, cy - 3, px, cy - 2], fill=color)
    for px, py in ((cx - 2, cy + 2), (cx + 1, cy + 2)):
        d.point((px, py), fill=(0, 0, 0, 0))


def sprite_origin(b: Dict[str, Any]) -> Tuple[int, int]:
    """Top-left screen px of a beat's sprite: horizontally centred on b['x']+16, feet on the row baseline."""
    return round(b["x"] + 16 - CENTER_X * SCALE), round(b["y"] + 21 - BASELINE_Y * SCALE)


def anchor_screen(b: Dict[str, Any], name: str) -> Tuple[float, float]:
    """Screen position of a named sprite anchor (nose / paw / baseline), honouring facing direction."""
    ax, ay = get_anchors(b["state"], b["frame"])[name]
    if b["facing_left"]:
        ax = 32 - ax
    ox, oy = sprite_origin(b)
    return ox + ax * SCALE, oy + ay * SCALE


def _x_for_anchor(state: str, frame: int, name: str, fl: bool, target_x: float) -> int:
    """Planner-style x that puts the named anchor on target_x."""
    ax = get_anchors(state, frame)[name][0]
    if fl:
        ax = 32 - ax
    return round(target_x - ax * SCALE + CENTER_X * SCALE - 16)


def _smooth(t: float) -> float:
    s = t * t * (3 - 2 * t)
    return 0.65 * s + 0.35 * t          # eased but never stalls completely


def _short_status(s: str) -> str:
    s = s.replace("✦", "").strip()
    if ":" in s:
        s = s.split(":", 1)[1].strip()
    return s[:70]


def expand_timeline(timeline: List[Dict[str, Any]], target_aligned: bool = True) -> List[Dict[str, Any]]:
    """Turn the planner's coarse timeline into the final beat list (adds 'dur', 'alpha', 'stamp')."""
    out: List[Dict[str, Any]] = []
    n = len(timeline)
    groups: List[List[Dict[str, Any]]] = []
    for it in timeline:
        if groups and groups[-1][0]["state"] == it["state"] and groups[-1][0].get("target") == it.get("target"):
            groups[-1].append(it)
        else:
            groups.append([it])

    def beat(src, **kw):
        b = {"x": src["x"], "y": src["y"], "facing_left": src["facing_left"], "state": src["state"],
             "frame": 0, "status": src["status"], "target": src.get("target"), "paws": set(src["paws"]),
             "sparkle": False, "dur": 100, "paw_alpha": 1.0, "stamp": None, "age": 0, "dy": 0}
        b.update(kw)
        return b

    last_pos = (timeline[0]["x"], timeline[0]["y"])
    for gi, g in enumerate(groups):
        st = g[0]["state"]
        first, last = g[0], g[-1]
        if st == "idle" and gi == 0:
            for k in range(8):                           # sleeping, breathing
                out.append(beat(first, state="rest", frame=k % 4, dur=240, status="Resting between patrols"))
            for k in range(4):                           # stretch + blink awake
                out.append(beat(first, state="idle", frame=k, dur=150, status="Waking up..."))
        elif st == "idle":                               # final: settle back to sleep, paws fade
            for k in range(4):
                out.append(beat(first, state="idle", frame=k, dur=150, status="Back on guard"))
            alphas = [0.8, 0.6, 0.4, 0.25, 0.12, 0.0]
            for k, a in enumerate(alphas):
                out.append(beat(first, state="rest", frame=k % 4, dur=170, paw_alpha=a,
                                status="Resting between patrols"))
            out[-1]["dur"] = 400
            out[-1]["frame"] = 0
        elif st == "run":
            pts = [last_pos] + [(it["x"], it["y"]) for it in g]
            total = len(g) * 3
            fl = first["facing_left"]
            for k in range(1, total + 1):
                t = _smooth(k / total)
                seg = t * (len(pts) - 1)
                i0 = min(int(seg), len(pts) - 2)
                f = seg - i0
                x = round(pts[i0][0] + (pts[i0 + 1][0] - pts[i0][0]) * f)
                y = round(pts[i0][1] + (pts[i0 + 1][1] - pts[i0][1]) * f)
                slow = k <= 3 or k > total - 3
                out.append(beat(g[min(k // 3, len(g) - 1)], x=x, y=y, facing_left=fl,
                                state="walk" if slow else "run", frame=k,
                                dur=95 if slow else 62))
            last_pos = (last["x"], last["y"])
        elif st == "look_around":
            for k in range(8):
                out.append(beat(first, state="look_around", frame=k // 2, dur=170))
        elif st in ("sniff", "paw_touch", "happy"):
            tgt = first.get("target")
            x, y, fl = first["x"], first["y"], first["facing_left"]
            tcx = GX + tgt["col"] * STEP + CELL / 2 if tgt else None
            if tgt and target_aligned:
                if st == "sniff":
                    x = _x_for_anchor("sniff", 0, "nose", fl, tcx)
                else:
                    x = _x_for_anchor("paw_touch", 3, "paw", fl, tcx)
            if st == "sniff":
                for k in range(8):
                    lerp = min(1.0, (k + 1) / 3.0)
                    px = round(last_pos[0] + (x - last_pos[0]) * lerp)
                    out.append(beat(first, x=px, y=y, state="sniff", frame=k, dur=115, sparkle=True, age=k))
            elif st == "paw_touch":
                for k in range(6):
                    b = beat(first, x=x, y=y, state="paw_touch", frame=k, dur=(160, 120, 140, 230, 130, 130)[k],
                             sparkle=True, age=8 + k)
                    if tgt:
                        cell = (tgt["col"], tgt["row"])
                        b["paws"].discard(cell)
                        if k >= 3:
                            b["paws"].add(cell)
                        if k == 3:
                            b["stamp"] = cell
                    out.append(b)
            else:
                for k in range(6):
                    out.append(beat(first, x=x, y=y, state="happy", frame=k, dur=120, age=14 + k,
                                    sparkle=k < 2))
            last_pos = (x, y)
    return out


def _paw_layer(paws: Set[Tuple[int, int]], alpha: float, stamp_age: Dict[Tuple[int, int], int]) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (c, r) in paws:
        x0, y0 = cell_origin(c, r)
        a = int(PAW_COLOR[3] * alpha)
        if a <= 0:
            continue
        age = stamp_age.get((c, r), 99)
        col = (255, 255, 255, a) if age == 0 else PAW_COLOR[:3] + (a,)
        draw_pawprint(d, x0 + CELL // 2, y0 + CELL // 2 - 1, col)
    return layer


def render_gif(
    grid_days: Dict[Tuple[int, int], Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    total_commits: int,
    peak_day: Dict[str, Any] | None,
    username: str = "SamSurve",
    output_path: str = "dist/contribution-doggo.gif",
) -> None:
    t0 = time.time()
    f_title, f_sub, f_small = get_font(17), get_font(12), get_font(10)

    # ---- static base card (includes the whole grid; only effects change per frame)
    base = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([14, 12, W - 15, H - 13], radius=14, fill=PANEL, outline=BORDER, width=1)
    icon = render_corgi_frame("idle", 0)
    base.paste(icon, (38, 24), icon)
    d.text((80, 24), "Contribution Doggo", fill=TEXT, font=f_title)
    d.text((80, 48), f"@{username}  ·  {total_commits:,} contributions in the last year", fill=MUTED, font=f_sub)
    if peak_day:
        s = f"Best day  {peak_day['count']} on {peak_day['date']}"
        d.text((W - 38 - d.textlength(s, font=f_sub), 34), s, fill=MUTED, font=f_sub)

    last_month = None
    for col in range(WEEKS):
        info = next((grid_days.get((col, r)) for r in range(7) if (col, r) in grid_days), None)
        if info:
            dt = date.fromisoformat(info["date"])
            if dt.month != last_month:
                last_month = dt.month
                d.text((GX + col * STEP, GY - 17), MONTHS[dt.month - 1], fill=FAINT, font=f_small)
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        d.text((GX - 34, GY + r * STEP + 1), name, fill=FAINT, font=f_small)
    for col in range(WEEKS):
        for row in range(7):
            info = grid_days.get((col, row))
            lvl = info["level"] if info else 0
            x0, y0 = cell_origin(col, row)
            d.rounded_rectangle([x0, y0, x0 + CELL - 1, y0 + CELL - 1], radius=2, fill=LEVELS[lvl])

    lx, ly = W - 214, H - 40
    d.text((lx - 32, ly - 1), "Less", fill=FAINT, font=f_small)
    for i, c in enumerate(LEVELS):
        d.rounded_rectangle([lx + i * 15, ly, lx + i * 15 + 10, ly + 10], radius=2, fill=c)
    d.text((lx + 5 * 15 + 4, ly - 1), "More", fill=FAINT, font=f_small)

    # ---- expand + render
    beats = expand_timeline(timeline)
    sprites: Dict[Tuple[str, int, bool], Image.Image] = {}
    stamp_seen: Dict[Tuple[int, int], int] = {}
    rgb_frames: List[Image.Image] = []
    durations: List[int] = []
    counts: Counter = Counter()

    for idx, b in enumerate(beats):
        fr = base.copy()
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        tgt = b["target"]

        if b["stamp"]:
            stamp_seen[b["stamp"]] = idx
        stamp_age = {k: idx - v for k, v in stamp_seen.items()}
        paws = b["paws"]

        # target highlight: soft tint + hairline ring, eased in
        if tgt and (b["sparkle"] or b["state"] in ("paw_touch", "happy")):
            tx0, ty0 = cell_origin(tgt["col"], tgt["row"])
            k = min(1.0, (b["age"] + 1) / 3.0) if b["state"] != "happy" else max(0.0, 1 - (b["age"] - 14) / 5.0)
            od.rounded_rectangle([tx0, ty0, tx0 + CELL - 1, ty0 + CELL - 1], radius=2,
                                 fill=(255, 226, 150, int(70 * k)))
            od.rounded_rectangle([tx0 - 2, ty0 - 2, tx0 + CELL + 1, ty0 + CELL + 1], radius=4,
                                 outline=GOLD + (int(210 * k),), width=1)
            if b["state"] == "sniff":                    # scent wisps: three tiny rising dots
                for j in range(3):
                    ph = (b["frame"] * 0.5 + j * 0.9) % 3.0
                    sx = tx0 + 2 + j * 4 + round(math.sin(ph * 2.2 + j) * 1.5)
                    sy = ty0 - 4 - int(ph * 3)
                    od.rectangle([sx, sy, sx + 1, sy + 1], fill=(255, 236, 190, int(200 * (1 - ph / 3.2))))
            if b["stamp"] or (stamp_age.get((tgt["col"], tgt["row"]), 99) in (1, 2)):
                a = stamp_age.get((tgt["col"], tgt["row"]), 0)
                rr = 8 + a * 2
                cx, cy = tx0 + CELL // 2, ty0 + CELL // 2
                od.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 236, 190, 150 - 55 * a), width=1)

        fr = Image.alpha_composite(fr, ov)
        fr = Image.alpha_composite(fr, _paw_layer(paws, b["paw_alpha"], {k: v for k, v in stamp_age.items() if v == 0}))

        # dog: shadow + sprite
        key = (b["state"], b["frame"], b["facing_left"])
        if key not in sprites:
            s = render_corgi_frame(*key)
            sprites[key] = s.resize((SPR_W, SPR_H), Image.NEAREST)
        spr = sprites[key]
        sx, sy = sprite_origin(b)
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([sx + 6, sy + SPR_H - 4, sx + SPR_W - 6, sy + SPR_H + 2], fill=(0, 0, 0, 70))
        fr = Image.alpha_composite(fr, sh)
        fr.alpha_composite(spr, (sx, sy)) if 0 <= sx <= W - SPR_W and 0 <= sy <= H - SPR_H else fr.paste(spr, (sx, sy), spr)

        # status line
        dd = ImageDraw.Draw(fr)
        pulse = 1 if b["state"] == "rest" else (idx // 3) % 2
        dd.ellipse([38, H - 38, 44, H - 32], fill=(63, 185, 80) if pulse else (46, 140, 62))
        dd.text((54, H - 41), _short_status(b["status"]), fill=MUTED, font=f_sub)
        if b["state"] == "rest":                          # tiny pixel "z"
            zk = b["frame"] % 4
            zx, zy = sx + 40 + zk * 2, sy - 2 - zk * 2
            for (px, py) in ((0, 0), (1, 0), (2, 0), (2, 1), (1, 2), (0, 3), (0, 4), (1, 4), (2, 4)):
                dd.rectangle([zx + px * 2, zy + py * 2, zx + px * 2 + 1, zy + py * 2 + 1], fill=FAINT if zk % 2 == 0 else MUTED)

        rgb = fr.convert("RGB")
        rgb_frames.append(rgb)
        durations.append(b["dur"])
        counts.update({c: n for n, c in rgb.getcolors(W * H)})

    # ---- one shared palette for every frame (no flicker, crisp pixels, no dithering)
    must = [tuple(v[:3]) for v in SPRITE_PALETTE.values() if v[3]] + LEVELS + [BG, PANEL, BORDER, TEXT, MUTED, FAINT, GOLD]
    colors = list(dict.fromkeys(must))
    for c, _ in counts.most_common():
        if len(colors) >= 255:
            break
        if c not in colors:
            colors.append(c)
    pal = Image.new("P", (1, 1))
    flat = [v for c in colors for v in c] + [0] * (768 - 3 * len(colors))
    pal.putpalette(flat)
    frames = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in rgb_frames]

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out_file, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=False)
    print(f"Successfully generated {out_file} ({len(frames)} frames, {sum(durations)/1000:.1f}s) "
          f"in {time.time()-t0:.2f}s! Size: {out_file.stat().st_size / 1024:.1f} KB")
