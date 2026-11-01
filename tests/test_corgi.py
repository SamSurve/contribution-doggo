"""
Tests for pixel-art corgi sprite rendering.
"""
from PIL import Image

from src.corgi import render_corgi_frame


def test_sprite_dimensions():
    for state in ["idle", "run", "sniff", "paw_touch", "happy", "look_around"]:
        for frame in range(4):
            for flip in [False, True]:
                spr = render_corgi_frame(state, frame, facing_left=flip)
                assert isinstance(spr, Image.Image)
                assert spr.size == (32, 22), f"Sprite {state} frame {frame} size is {spr.size}, expected (32, 22)"
                assert spr.mode == "RGBA"


def test_sprite_has_content():
    spr = render_corgi_frame("run", 0, facing_left=False)
    # Check that non-transparent pixels exist
    alpha_channel = spr.split()[3]
    bbox = alpha_channel.getbbox()
    assert bbox is not None, "Sprite should contain non-transparent pixels"


def test_horizontal_flip():
    spr_right = render_corgi_frame("run", 0, facing_left=False)
    spr_left = render_corgi_frame("run", 0, facing_left=True)
    assert spr_right != spr_left
    flipped_right = spr_right.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    assert list(spr_left.tobytes()) == list(flipped_right.tobytes())
