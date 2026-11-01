"""Visual and rendering QA tests for Contribution Doggo v2."""
import random
from datetime import date, timedelta

from PIL import Image

from src.corgi import FRAME_COUNT, PALETTE, STATES, get_anchors, render_corgi_frame
from src.planner import build_timeline
from src import renderer as R


def _grid():
    random.seed(1)
    start, grid, active = date(2025, 11, 2), {}, []
    for c in range(53):
        for r in range(7):
            n = random.choice([0, 0, 1, 3, 6])
            it = {
                "date": (start + timedelta(days=c * 7 + r)).isoformat(),
                "count": n,
                "level": 0 if not n else min(4, 1 + n // 2),
                "col": c,
                "row": r,
            }
            grid[(c, r)] = it
            if n:
                active.append(it)
    peak = max(active, key=lambda i: i["count"])
    return grid, active, sum(i["count"] for i in grid.values()), peak


def _beats():
    grid, active, tot, peak = _grid()
    return grid, active, tot, peak, build_timeline(grid, active, tot, peak)


def test_all_states_sprite_size_and_content():
    for s in STATES:
        for f in range(FRAME_COUNT[s]):
            for flip in (False, True):
                img = render_corgi_frame(s, f, flip)
                assert img.size == (32, 22) and img.mode == "RGBA"
                assert img.getchannel("A").getbbox() is not None


def test_pawprint_fits_inside_cell():
    for col, row in ((0, 0), (26, 3), (52, 6)):
        layer = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        R.draw_pawprint(
            __import__("PIL.ImageDraw", fromlist=["x"]).Draw(layer),
            R.cell_origin(col, row)[0] + R.CELL // 2,
            R.cell_origin(col, row)[1] + R.CELL // 2 - 1,
        )
        x0, y0 = R.cell_origin(col, row)
        bx0, by0, bx1, by1 = layer.getchannel("A").getbbox()
        assert x0 <= bx0 and bx1 <= x0 + R.CELL and y0 <= by0 and by1 <= y0 + R.CELL


def test_grid_bounds_and_expanded_timeline():
    grid, active, tot, peak = _grid()
    beats = R.expand_timeline(build_timeline(grid, active, tot, peak))
    assert beats[0]["state"] == "rest" and beats[-1]["state"] == "rest"
    assert beats[-1]["paw_alpha"] == 0.0  # paws fade out -> clean loop seam
    assert (beats[0]["x"], beats[0]["y"]) == (beats[-1]["x"], beats[-1]["y"])
    for b in beats:
        if b["target"]:
            assert 0 <= b["target"]["col"] < R.WEEKS and 0 <= b["target"]["row"] < 7


def test_nose_pixels_rendered_and_anchors_mirror():
    for s in STATES:
        for fl in (False, True):
            img = render_corgi_frame(s, 0, fl)
            px = img.load()
            has_nose = any(px[x, y] == PALETTE["nose"] for x in range(32) for y in range(22))
            assert has_nose, f"Missing nose pixel in state {s}, facing_left={fl}"
    ax = get_anchors("sniff", 0)["nose"][0]
    mir = render_corgi_frame("sniff", 0, True)
    px_m = mir.load()
    nx = [x for x in range(32) for y in range(22) if px_m[x, y] == PALETTE["nose"]]
    assert abs((sum(nx) / len(nx) + 0.5) - (32 - ax)) < 0.6


def test_paw_contact_inside_target_square_both_directions():
    grid, active, tot, peak, tl = _beats()
    seen_paw = set()
    seen_sniff = set()
    for b in R.expand_timeline(tl):
        if b["state"] == "paw_touch" and b["frame"] == 3:
            px, py = R.anchor_screen(b, "paw")
            x0, y0 = R.cell_origin(b["target"]["col"], b["target"]["row"])
            assert x0 <= px <= x0 + R.CELL and y0 <= py <= y0 + R.CELL, (px, py, x0, y0)
            assert b["stamp"] == (b["target"]["col"], b["target"]["row"])
            seen_paw.add(b["facing_left"])
        if b["state"] == "sniff" and b["frame"] == 7:
            nx, ny = R.anchor_screen(b, "nose")
            x0, y0 = R.cell_origin(b["target"]["col"], b["target"]["row"])
            assert x0 <= nx <= x0 + R.CELL and y0 <= ny <= y0 + R.CELL, (nx, ny, x0, y0)
            seen_sniff.add(b["facing_left"])
    # 1. Must verify that both directions were actually tested
    assert seen_paw == {False, True}, f"Expected paw touch in both directions, saw {seen_paw}"
    assert seen_sniff == {False, True}, f"Expected sniff in both directions, saw {seen_sniff}"


def test_actual_paw_anchor_alignment_x_and_y():
    # 2. Test actual paw anchor alignment in both X and Y directions
    target_col, target_row = 25, 3
    x0, y0 = R.cell_origin(target_col, target_row)
    tcx = x0 + R.CELL / 2.0
    for fl in (False, True):
        dog_x = R._x_for_anchor("paw_touch", 3, "paw", fl, tcx)
        dog_y = y0 + R.CELL - 20
        b = {
            "x": dog_x,
            "y": dog_y,
            "facing_left": fl,
            "state": "paw_touch",
            "frame": 3,
            "target": {"col": target_col, "row": target_row},
        }
        px, py = R.anchor_screen(b, "paw")
        # X must fall directly inside the target cell
        assert x0 <= px <= x0 + R.CELL, f"Paw X {px} not in cell [{x0}, {x0+R.CELL}] (fl={fl})"
        # Y must touch down inside the target cell
        assert y0 <= py <= y0 + R.CELL, f"Paw Y {py} not in cell [{y0}, {y0+R.CELL}] (fl={fl})"


def test_sniff_nose_alignment_both_directions():
    # 3. Verify sniff nose alignment against the target square in both directions
    target_col, target_row = 30, 2
    x0, y0 = R.cell_origin(target_col, target_row)
    tcx = x0 + R.CELL / 2.0
    for fl in (False, True):
        dog_x = R._x_for_anchor("sniff", 0, "nose", fl, tcx)
        dog_y = y0 + R.CELL - 20
        b = {
            "x": dog_x,
            "y": dog_y,
            "facing_left": fl,
            "state": "sniff",
            "frame": 7,  # frame 7 % 4 = 3
            "target": {"col": target_col, "row": target_row},
        }
        nx, ny = R.anchor_screen(b, "nose")
        assert x0 <= nx <= x0 + R.CELL, f"Nose X {nx} not in cell [{x0}, {x0+R.CELL}] (fl={fl})"
        assert y0 <= ny <= y0 + R.CELL, f"Nose Y {ny} not in cell [{y0}, {y0+R.CELL}] (fl={fl})"


def test_sprite_anchors_accuracy_all_frames():
    # 4. Ensure sprite anchors are accurate for every relevant animation frame
    for s in STATES:
        for f in range(FRAME_COUNT[s]):
            anchors = get_anchors(s, f)
            assert "baseline" in anchors
            bx, by = anchors["baseline"]
            assert bx == R.CENTER_X and by == R.BASELINE_Y

            assert "nose" in anchors
            nx, ny = anchors["nose"]
            assert 0 <= nx <= 32 and 0 <= ny <= 22

            if s == "paw_touch" and f in (1, 2, 3, 4):
                assert "paw" in anchors, f"Expected paw anchor in paw_touch frame {f}"
                paw_x, paw_y = anchors["paw"]
                assert 0 <= paw_x <= 32 and 0 <= paw_y <= 22


def test_forced_both_facings_align():
    for fl in (False, True):
        b = {
            "x": R._x_for_anchor("paw_touch", 3, "paw", fl, 300.0),
            "y": 200,
            "facing_left": fl,
            "state": "paw_touch",
            "frame": 3,
        }
        assert abs(R.anchor_screen(b, "paw")[0] - 300.0) <= 1


def test_rendered_pixels_and_loop_identical(tmp_path):
    from PIL import ImageChops

    grid, active, tot, peak, tl = _beats()
    out = tmp_path / "t.gif"
    R.render_gif(grid, tl, tot, peak, "x", str(out))
    im = Image.open(out)
    assert im.size == (R.W, R.H) and im.n_frames > 100 and im.info.get("loop") == 0
    first = im.convert("RGB").copy()
    im.seek(im.n_frames - 1)
    last = im.convert("RGB")
    assert ImageChops.difference(first, last).getbbox() is None  # pixel-identical seam
    beats = R.expand_timeline(tl)
    assert beats[-1]["paws"] and beats[-1]["paw_alpha"] == 0.0
