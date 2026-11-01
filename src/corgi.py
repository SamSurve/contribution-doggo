"""
Contribution Doggo sprite engine (v2).

Hand-authored pixel parts (ASCII maps) are composed into 32x22 RGBA frames.
Each part is auto-outlined so line weight stays consistent. The renderer scales
frames 2x with nearest-neighbour, so edges stay crisp.

Public API (unchanged): render_corgi_frame(state, frame, facing_left) -> 32x22 RGBA.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Tuple

from PIL import Image

SPRITE_W, SPRITE_H = 32, 22

PALETTE = {
    "trans": (0, 0, 0, 0),
    "outline": (62, 34, 24, 255),
    "fur": (226, 134, 48, 255),
    "fur_hi": (246, 176, 84, 255),
    "fur_dark": (176, 94, 34, 255),
    "white": (255, 249, 240, 255),
    "white_sh": (216, 212, 224, 255),
    "cream": (255, 222, 186, 255),
    "pink": (238, 140, 140, 255),
    "black": (26, 20, 30, 255),
    "nose": (34, 22, 40, 255),
    "collar": (70, 104, 214, 255),
    "tag": (252, 208, 64, 255),
    "tongue": (236, 96, 124, 255),
}
_C = {"f": "fur", "h": "fur_hi", "d": "fur_dark", "w": "white", "s": "white_sh", "c": "cream",
      "p": "pink", "k": "black", "e": "white", "t": "tongue", "b": "collar", "g": "tag", "o": "outline", "n": "nose"}

BODY = [
    "..hhhhhhhhhhhhhhhh....",
    ".hhhhhhhhhhhhhhhhhhff.",
    "ffhhhhhhhhhhhhhhfffffw",
    "fffffffffffffffffffwww",
    "ffffffffffffffffffwwww",
    "ffffffffffffffffffwwww",
    ".dfffffffffffffffwwwws",
    "..ddddddddddddddwwwwss",
    "....dddddddddddddwwss.",
]
HEAD = [          # side view facing right, 13x10
    "..ffhhhhff...",
    ".fffffffffff.",
    "fffffffffwwff",
    "fffffkkffwwwf",
    "fffffkekfwwwww",
    "ffffffffwwwwwc",
    ".ffffffwwwwccn",
    ".fffwwwwwwcccn",
    "..swwwwwwwwwnn",
    "....sswwwwwss.",
]
HEAD_FRONT = [    # facing viewer, 11x10
    "...ffffff..",
    "..ffffffff.",
    ".ffffwwffff",
    "ffkkfwwfkkf",
    "ffkefwwfkef",
    "fffffwwfffff"[:11],
    ".fffwwwwfff",
    ".fffwcccwff"[:11],
    "..swwcnnws..",
    "....swwws...",
]
EAR_UP = ["...ff..", "..fpff.", "..fppff", ".fppppf", ".fpppff", "ffpppff", "ffffff."]
EAR_BACK = ["f......", "ffff...", "fppff..", ".fppff.", "..ffff.", "...fff."]
EAR_PERK = ["..fff..", ".fppff.", ".fpppf.", "ffpppff", "ffppfff", "fffff.."]
EAR_FLOP = ["......", "..fff.", ".fppff", "fppppf", "ffppf.", ".ffff."]


def _parse(rows: List[str], dark: bool = False) -> Dict[Tuple[int, int], Tuple[int, int, int, int]]:
    out = {}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in _C:
                name = _C[ch]
                if dark and ch in "fhp":
                    name = "fur_dark" if ch != "p" else "fur_dark"
                out[(x, y)] = PALETTE[name]
    return out


def _stamp(cv: Dict, art: Dict, ox: int, oy: int, outline: bool = True) -> None:
    pts = {(x + ox, y + oy): c for (x, y), c in art.items()}
    if outline:
        for (x, y) in list(pts):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (x + dx, y + dy)
                if q not in pts and q not in cv:
                    cv[q] = PALETTE["outline"]
                elif q not in pts and cv.get(q) != PALETTE["outline"]:
                    cv[q] = PALETTE["outline"]
    cv.update(pts)


def _leg(cv, hx, hy, fx, fy, near=True, lift=False):
    """Short sturdy leg from hip (hx,hy) to foot (fx,fy), 3px wide, white sock."""
    art = {}
    h = max(1, fy - hy)
    for i in range(h + 1):
        t = i / h
        x = round(hx + (fx - hx) * t)
        y = hy + i
        sock = i >= h - 1
        base = ("white" if sock else "fur") if near else ("white_sh" if sock else "fur_dark")
        for dx in range(3):
            art[(x + dx, y)] = PALETTE[base]
    _stamp(cv, art, 0, 0)


def _tail(cv, x, y, wag):
    art = _parse(["hff", "fffw", "ffw."] if wag >= 0 else [".ff", "fffw", "hfw."])
    _stamp(cv, art, x, y + (-wag if wag > 0 else -wag))


# gait tables: (back_far, back_near, front_far, front_near) = (dx, dy) foot offsets vs rest
STAND = ((0, 0), (0, 0), (0, 0), (0, 0))
WALK = [
    ((-2, 0), (2, -1), (2, -1), (-2, 0)),
    ((-1, 0), (1, 0), (1, 0), (-1, 0)),
    ((1, -1), (-2, 0), (-2, 0), (2, -1)),
    ((2, -1), (-1, 0), (-1, 0), (1, 0)),
    ((1, 0), (0, 0), (0, 0), (1, 0)),
    ((0, 0), (1, 0), (1, 0), (0, 0)),
]
RUN = [  # gallop: gather -> extend, body bob handled separately
    ((-4, -1), (-3, 0), (4, -2), (5, -1)),
    ((-3, 0), (-2, 0), (3, -1), (4, 0)),
    ((1, 0), (2, -1), (-1, 0), (0, 0)),
    ((3, -2), (4, -1), (-3, -1), (-2, 0)),
    ((2, -1), (3, 0), (-4, 0), (-3, 0)),
    ((-1, 0), (0, 0), (1, 0), (2, 0)),
]
RUN_BOB = [0, 1, 1, 0, -1, -1]
WALK_BOB = [0, 1, 0, 0, 1, 0]


_PAW: Dict[Tuple[str, int], Tuple[int, int]] = {}


def _compose(state: str, frame: int) -> Dict:
    cv: Dict = {}
    f = frame
    bob = 0
    head_dx = head_dy = 0
    ears = EAR_UP
    gait = STAND
    wag = 0
    tongue = blink = False
    front = False
    paw = None          # (dx, dy) reach for near front paw
    lying = False
    ear_dy = 0

    if state == "idle":
        f %= 4
        bob = (0, 0, 1, 1)[f] * 0
        head_dy = (0, 0, 1, 1)[f] if f in (2, 3) else 0
        wag = (0, 1, 0, -1)[f]
        blink = (f == 3)
    elif state == "walk":
        f %= 6
        gait, bob, wag = WALK[f], WALK_BOB[f], (1, 0, -1, 0, 1, 0)[f]
        head_dy = WALK_BOB[f] - 1 if WALK_BOB[f] else 0
    elif state == "run":
        f %= 6
        gait, bob, ears = RUN[f], RUN_BOB[f], EAR_BACK
        wag = (2, 1, 0, -1, 0, 1)[f]
        tongue = f in (2, 3)
        head_dx, head_dy = 1, -1 if bob >= 1 else 0
    elif state == "look_around":
        f %= 4
        front = f in (1, 2)
        head_dx = (0, -1, -1, 0)[f]
        wag = (0, 1, 0, 1)[f]
        ears = EAR_PERK
        tongue = f == 2
    elif state == "sniff":
        f %= 4
        head_dx, head_dy, ears = 1, 5, EAR_FLOP
        bob = 1
        gait = ((0, 0), (0, 0), (1, 0), (1, 0))
        wag = (0, 1, 0, -1)[f]
    elif state == "paw_touch":
        # 0 anticipation (crouch) 1 lift 2 extend 3 contact 4 retract 5 settle
        f %= 6
        head_dx, ears = 1, EAR_PERK
        head_dy = (2, 1, 2, 3, 2, 0)[f]
        bob = (1, 0, 0, 1, 0, 0)[f]
        paw = (None, (22, 11), (27, 15), (27, 19), (23, 13), None)[f]
        ears = EAR_FLOP if f == 0 else EAR_PERK
        wag = (0, 0, 0, 1, 0, 1)[f]
    elif state == "happy":
        f %= 4
        bob = (0, -2, 0, -1)[f]
        wag = (3, -3, 3, -3)[f]
        tongue = True
        ears = EAR_UP
        head_dy = -1 if f == 1 else 0
        gait = ((0, 0), (0, bob), (0, 0), (0, bob)) if False else STAND
    elif state == "rest":
        f %= 4
        lying = True
        blink = f != 3
        bob = (0, 0, 1, 1)[f]
        ears = EAR_FLOP
        wag = 0
    else:
        raise ValueError(f"unknown state {state!r}")

    paw_art = None
    by = 8 + bob
    rest_y = 17  # standing hip->foot baseline

    if lying:
        by = 12 + bob
        # tucked far/near back legs & front paws forward
        _stamp(cv, _parse(["sss", "www"]), 6, 19 + 0)
        _tail(cv, 0, by + 3, 0)
        _stamp(cv, _parse(BODY), 2, by)
        _stamp(cv, _parse(["ffff", "wwww"]), 17, 19)
        _stamp(cv, _parse(["ffff", "wwww"]), 21, 19)
        hx, hy = 16, 10 + bob
        _stamp(cv, _parse(EAR_FLOP, dark=True), hx + 1, hy - 1)
        _stamp(cv, _parse(HEAD), hx, hy)
        _stamp(cv, _parse(EAR_FLOP), hx + 4, hy - 2)
        # closed eye + collar
        cv[(hx + 5, hy + 3)] = PALETTE["outline"]; cv[(hx + 6, hy + 3)] = PALETTE["outline"]
        cv[(hx + 5, hy + 4)] = PALETTE["fur"]; cv[(hx + 6, hy + 4)] = PALETTE["fur"]
        if f == 3:  # tiny peek
            cv[(hx + 5, hy + 4)] = PALETTE["black"]
        return cv

    # far legs
    bf, bn, ff, fn = gait
    base_hip_y = by + 7
    _leg(cv, 5 + bf[0], base_hip_y, 5 + bf[0] + (0 if bf[1] == 0 else 0), 20 + bf[1], near=False)
    _leg(cv, 17 + ff[0], base_hip_y, 17 + ff[0], 20 + ff[1], near=False)
    _tail(cv, 0, by + 1, wag)
    _stamp(cv, _parse(BODY), 2, by)
    # near legs
    _leg(cv, 8 + bn[0], base_hip_y, 8 + bn[0], 20 + bn[1], near=True)
    if paw:
        ex, ey = paw
        art = {}
        sx, sy = 18, by + 6
        steps = max(abs(ex - sx), abs(ey - sy), 1)
        for i in range(steps + 1):
            x = round(sx + (ex - sx) * i / steps)
            y = round(sy + (ey - sy) * i / steps)
            for dx in range(3):
                art[(x + dx, y)] = PALETTE["fur"]
        for dx in range(-1, 4):
            art[(ex + dx, ey)] = PALETTE["white"]
            art[(ex + dx, ey + 1)] = PALETTE["white"]
        paw_art = art
        _PAW[(state, f)] = (ex + 1, ey + 1)
    else:
        _leg(cv, 20 + fn[0], base_hip_y, 20 + fn[0], 20 + fn[1], near=True)

    # collar (drawn over chest)
    cx = 18 + head_dx
    for y in range(by + 1, by + 6):
        cv[(cx, y)] = PALETTE["collar"]; cv[(cx + 1, y)] = PALETTE["collar"]
    cv[(cx + 2, by + 6)] = PALETTE["tag"]; cv[(cx + 2, by + 7)] = PALETTE["tag"]

    hx, hy = 16 + head_dx, 4 + bob + head_dy
    head = HEAD_FRONT if front else HEAD
    ear_n = EAR_PERK if front else ears
    if front:
        _stamp(cv, _parse(EAR_UP), hx - 1, hy - 5)
        _stamp(cv, _parse(EAR_UP), hx + 5, hy - 5)
        _stamp(cv, _parse(head), hx, hy)
    else:
        _stamp(cv, _parse(ear_n, dark=True), hx + 1, hy - 3 + (1 if ear_n is EAR_FLOP else 0))
        _stamp(cv, _parse(head), hx, hy)
        _stamp(cv, _parse(ear_n), hx + 4, hy - 4 + (2 if ear_n is EAR_FLOP else 0) + (1 if ear_n is EAR_BACK else 0))
    if paw_art:
        _stamp(cv, paw_art, 0, 0)      # raised paw is drawn in front of the head
    if blink and not front:
        for x in (5, 6):
            cv[(hx + x, hy + 3)] = PALETTE["outline"]
            cv[(hx + x, hy + 4)] = PALETTE["fur"]
    if tongue and not front:
        for (x, y) in ((hx + 11, hy + 9), (hx + 12, hy + 9), (hx + 11, hy + 10), (hx + 12, hy + 10)):
            cv[(x, y)] = PALETTE["tongue"]
    elif tongue and front:
        for (x, y) in ((hx + 5, hy + 10), (hx + 6, hy + 10)):
            cv[(x, y)] = PALETTE["tongue"]
    return cv


@lru_cache(maxsize=None)
def _frame(state: str, frame: int) -> Image.Image:
    cv = _compose(state, frame)
    img = Image.new("RGBA", (SPRITE_W, SPRITE_H), (0, 0, 0, 0))
    px = img.load()
    for (x, y), c in cv.items():
        if 0 <= x < SPRITE_W and 0 <= y < SPRITE_H:
            px[x, y] = c
    return img


STATES = ("idle", "walk", "run", "look_around", "sniff", "paw_touch", "happy", "rest")
FRAME_COUNT = {"idle": 4, "walk": 6, "run": 6, "look_around": 4, "sniff": 4, "paw_touch": 6, "happy": 4, "rest": 4}


def render_corgi_frame(state: str = "run", frame: int = 0, facing_left: bool = False) -> Image.Image:
    """Return a 32x22 RGBA sprite. Facing right by default; flipped when facing_left."""
    img = _frame(state, frame % FRAME_COUNT[state]).copy()
    if facing_left:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return img


BASELINE_Y = 22          # bottom edge of the feet (sprite px, exclusive)
CENTER_X = 16            # horizontal body centre used for run/idle placement


def get_anchors(state: str, frame: int) -> Dict[str, Tuple[float, float]]:
    """Anchors in sprite px for the RIGHT-facing sprite; mirror x as (31 - x) when facing left.
    nose: centre of the nose pixels; paw: centre of the reaching paw's bottom (paw_touch only);
    baseline: (CENTER_X, BASELINE_Y)."""
    fr = frame % FRAME_COUNT[state]
    img = _frame(state, fr)
    px = img.load()
    pts = [(x, y) for x in range(SPRITE_W) for y in range(SPRITE_H) if px[x, y] == PALETTE["nose"]]
    out: Dict[str, Tuple[float, float]] = {"baseline": (CENTER_X, BASELINE_Y)}
    if pts:
        out["nose"] = (sum(p[0] for p in pts) / len(pts) + 0.5, sum(p[1] for p in pts) / len(pts) + 0.5)
    if (state, fr) in _PAW:
        x, y = _PAW[(state, fr)]
        out["paw"] = (x + 0.5, y + 0.5)
    return out
