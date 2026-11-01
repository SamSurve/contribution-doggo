"""
Pixel-art corgi sprite renderer for Contribution Doggo.
Generates pixel-crisp 32x22 RGBA sprite frames for each animation state.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

# Color Palette for Premium Pixel Art Corgi
PALETTE = {
    "trans":    (0, 0, 0, 0),
    "outline":  (48, 28, 16, 255),    # #301c10 Dark rich chocolate brown outline
    "fur":      (224, 122, 34, 255),   # #e07a22 Classic warm orange corgi coat
    "fur_hi":   (248, 168, 56, 255),   # #f8a838 Golden back highlight
    "fur_dark": (168, 80, 18, 255),    # #a85012 Shadow under belly and legs
    "white":    (255, 255, 255, 255),  # Pure white chest, blaze, socks
    "white_sh": (220, 224, 232, 255),  # Soft shadow white
    "cream":    (255, 228, 196, 255),  # Muzzle and inner ear light
    "pink":     (244, 114, 158, 255),  # Pink ear / tongue
    "black":    (18, 18, 24, 255),     # Nose & eye
    "collar":   (79, 70, 229, 255),    # Indigo collar
    "tag":      (245, 197, 24, 255),   # Gold medal tag
}


def render_corgi_frame(state: str = "run", frame: int = 0, facing_left: bool = False) -> Image.Image:
    """
    Renders a 32x22 pixel RGBA image of the corgi.
    States: 'idle', 'run', 'sniff', 'paw_touch', 'happy', 'look_around'.
    """
    img = Image.new("RGBA", (32, 22), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # State parameters
    bob_y = 0
    head_dy = 0
    head_dx = 0
    ears_mode = "up"       # "up", "forward", "look"
    tail_angle = 0        # -2 to +3
    tongue = False
    look_front = False
    paw_action = "normal"  # "normal", "lift", "touch"

    # Default standing leg positions (x, y)
    bl_x, bl_y = 5, 16
    br_x, br_y = 8, 16
    fl_x, fl_y = 17, 16
    fr_x, fr_y = 20, 16

    if state == "idle":
        bob_y = -1 if (frame % 2 == 1) else 0
        tail_angle = 1 if (frame % 2 == 1) else -1
    elif state == "look_around":
        look_front = True
        bob_y = 0
        tail_angle = 1
        tongue = (frame % 2 == 1)
    elif state == "run":
        f = frame % 4
        if f == 0:
            bob_y = 0
            tail_angle = 2
            bl_x, bl_y = 3, 16
            br_x, br_y = 7, 15
            fl_x, fl_y = 18, 15
            fr_x, fr_y = 23, 16
        elif f == 1:
            bob_y = 1
            tail_angle = 0
            bl_x, bl_y = 6, 16
            br_x, br_y = 8, 17
            fl_x, fl_y = 16, 17
            fr_x, fr_y = 19, 16
        elif f == 2:
            bob_y = 0
            tail_angle = -2
            bl_x, bl_y = 8, 16
            br_x, br_y = 4, 17
            fl_x, fl_y = 20, 16
            fr_x, fr_y = 16, 15
        elif f == 3:
            bob_y = -1
            tail_angle = 1
            bl_x, bl_y = 7, 15
            br_x, br_y = 9, 16
            fl_x, fl_y = 15, 16
            fr_x, fr_y = 19, 15
    elif state == "sniff":
        f = frame % 3
        head_dy = 2 + (1 if f == 1 else 0)
        head_dx = 1
        ears_mode = "forward"
        tail_angle = 2 if f == 1 else 0
        bob_y = 1
        fr_x, fr_y = 21, 17
        fl_x, fl_y = 16, 17
    elif state == "paw_touch":
        head_dy = 1
        ears_mode = "forward"
        paw_action = "touch"
        fr_x, fr_y = 24, 18
        tail_angle = 2
    elif state == "happy":
        tongue = True
        bob_y = -1 if (frame % 2 == 1) else 0
        tail_angle = 3 if (frame % 2 == 1) else -3

    by = 7 + bob_y

    # 1. Tail (Furry fluffy corgi tail / rump nub)
    ty = by + 2 - tail_angle
    d.polygon([(1, ty+2), (4, ty), (6, ty+3), (3, ty+4)], fill=PALETTE["fur"], outline=PALETTE["outline"])
    d.point((1, ty+2), fill=PALETTE["white"])
    d.point((2, ty+2), fill=PALETTE["white"])

    # 2. Far Legs (Drawn behind body)
    # Far back leg (bl)
    d.rectangle([bl_x, bl_y, bl_x+2, bl_y+3], fill=PALETTE["fur_dark"])
    d.rectangle([bl_x, bl_y+3, bl_x+2, bl_y+4], fill=PALETTE["white_sh"])
    d.rectangle([bl_x, bl_y, bl_x+2, bl_y+4], outline=PALETTE["outline"])

    # Far front leg (fl)
    d.rectangle([fl_x, fl_y, fl_x+2, fl_y+3], fill=PALETTE["fur_dark"])
    d.rectangle([fl_x, fl_y+3, fl_x+2, fl_y+4], fill=PALETTE["white_sh"])
    d.rectangle([fl_x, fl_y, fl_x+2, fl_y+4], outline=PALETTE["outline"])

    # 3. Body (Torso, flank, belly)
    d.rounded_rectangle([4, by, 20, by+9], radius=3, fill=PALETTE["fur"], outline=PALETTE["outline"])
    # Golden spine highlight
    d.line([8, by+1, 16, by+1], fill=PALETTE["fur_hi"])
    d.line([9, by+2, 17, by+2], fill=PALETTE["fur_hi"])
    # Belly shadow
    d.line([5, by+8, 12, by+8], fill=PALETTE["fur_dark"])
    # White belly & chest ruff
    d.ellipse([11, by+4, 18, by+9], fill=PALETTE["white"])
    d.ellipse([16, by+1, 21, by+8], fill=PALETTE["white"])

    # 4. Near Legs (Drawn in front of body)
    # Near back leg (br)
    d.rectangle([br_x, br_y, br_x+2, br_y+3], fill=PALETTE["fur"])
    d.rectangle([br_x, br_y+3, br_x+2, br_y+4], fill=PALETTE["white"])
    d.rectangle([br_x, br_y, br_x+2, br_y+4], outline=PALETTE["outline"])

    # Near front leg (fr)
    if paw_action == "touch":
        d.line([19, by+7, fr_x, fr_y], fill=PALETTE["fur"], width=3)
        d.rectangle([fr_x-1, fr_y-1, fr_x+2, fr_y+1], fill=PALETTE["white"], outline=PALETTE["outline"])
    else:
        d.rectangle([fr_x, fr_y, fr_x+2, fr_y+3], fill=PALETTE["fur"])
        d.rectangle([fr_x, fr_y+3, fr_x+2, fr_y+4], fill=PALETTE["white"])
        d.rectangle([fr_x, fr_y, fr_x+2, fr_y+4], outline=PALETTE["outline"])

    # 5. Collar & Tag
    d.line([19, by+2, 20, by+7], fill=PALETTE["collar"], width=2)
    d.point((20, by+6), fill=PALETTE["tag"])
    d.point((21, by+6), fill=PALETTE["tag"])

    # 6. Head & Face
    hx = 19 + head_dx
    hy = 3 + bob_y + head_dy

    # Ears
    if ears_mode == "up":
        # Far ear
        d.polygon([(hx+1, hy+2), (hx+2, hy-4), (hx+5, hy+1)], fill=PALETTE["fur_dark"], outline=PALETTE["outline"])
        d.point((hx+3, hy-2), fill=PALETTE["pink"])
        # Near ear
        d.polygon([(hx+4, hy+2), (hx+7, hy-5), (hx+10, hy+2)], fill=PALETTE["fur"], outline=PALETTE["outline"])
        d.polygon([(hx+5, hy+1), (hx+7, hy-3), (hx+9, hy+1)], fill=PALETTE["pink"])
    elif ears_mode == "forward":
        d.polygon([(hx+2, hy+3), (hx+4, hy-2), (hx+7, hy+3)], fill=PALETTE["fur_dark"], outline=PALETTE["outline"])
        d.polygon([(hx+5, hy+3), (hx+9, hy-3), (hx+11, hy+3)], fill=PALETTE["fur"], outline=PALETTE["outline"])
        d.point((hx+8, hy-1), fill=PALETTE["pink"])
    elif ears_mode == "look":
        d.polygon([(hx-1, hy+2), (hx+1, hy-4), (hx+4, hy+2)], fill=PALETTE["fur"], outline=PALETTE["outline"])
        d.polygon([(hx+6, hy+2), (hx+9, hy-4), (hx+11, hy+2)], fill=PALETTE["fur"], outline=PALETTE["outline"])

    # Head base rounded rectangle
    d.rounded_rectangle([hx, hy+2, hx+8, hy+8], radius=3, fill=PALETTE["fur"], outline=PALETTE["outline"])

    # Face details
    if look_front:
        d.rectangle([hx+2, hy+4, hx+3, hy+5], fill=PALETTE["black"])
        d.point((hx+2, hy+4), fill=PALETTE["white"])
        d.rectangle([hx+6, hy+4, hx+7, hy+5], fill=PALETTE["black"])
        d.point((hx+6, hy+4), fill=PALETTE["white"])
        d.rectangle([hx+4, hy+3, hx+5, hy+7], fill=PALETTE["white"])
        d.rectangle([hx+3, hy+6, hx+6, hy+8], fill=PALETTE["cream"], outline=PALETTE["outline"])
        d.point((hx+4, hy+6), fill=PALETTE["black"])
        d.point((hx+5, hy+6), fill=PALETTE["black"])
    else:
        d.rectangle([hx+3, hy+4, hx+6, hy+8], fill=PALETTE["white"])
        d.rectangle([hx+4, hy+3, hx+5, hy+5], fill=PALETTE["black"])
        d.point((hx+4, hy+3), fill=PALETTE["white"])
        snout_y = hy + 4 + (1 if ears_mode == "forward" else 0)
        d.rounded_rectangle([hx+6, snout_y, hx+10, snout_y+3], radius=1, fill=PALETTE["cream"], outline=PALETTE["outline"])
        d.rectangle([hx+9, snout_y, hx+10, snout_y+1], fill=PALETTE["black"])

    # Tongue
    if tongue:
        d.rectangle([hx+7, hy+7, hx+9, hy+9], fill=PALETTE["pink"])
        d.line([hx+8, hy+7, hx+8, hy+8], fill=(210, 60, 100, 255))

    if facing_left:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    return img
