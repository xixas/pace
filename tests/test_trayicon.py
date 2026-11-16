from pace import trayicon

TRAY = {"number": "30", "fill": 0.71}


def px(data, size, x, y):
    i = (y * size + x) * 4
    return tuple(data[i : i + 4])  # A, R, G, B


def ring_left(data, w, h):
    return px(data, w, 5, h // 2)  # centre of the ring stroke at 64 px


def ring_right(data, w, h):
    return px(data, w, w - 6, h // 2)


def test_pixmaps_sizes_and_format():
    pms = trayicon.pixmaps("green", TRAY)
    assert [(w, h) for w, h, _ in pms] == [(22, 22), (32, 32), (48, 48), (64, 64)]
    for w, h, data in pms:
        assert isinstance(data, bytes) and len(data) == w * h * 4


def test_corner_is_transparent_and_ring_is_verdict_colour():
    w, h, data = trayicon.pixmaps("green", {"number": "30", "fill": 1.0})[3]
    assert px(data, w, 0, 0)[0] == 0
    assert ring_left(data, w, h) == (255, 0x57, 0xE3, 0x89)


def test_grey_for_offline_colour():
    w, h, data = trayicon.pixmaps("grey", {"number": "26", "fill": 1.0})[3]
    assert ring_left(data, w, h) == (255, 0x9A, 0x99, 0x96)


def test_unfilled_part_of_ring_is_dimmer_than_filled():
    # fill runs clockwise from 12 o'clock: at 40% the right side is filled, the left is track only
    w, h, data = trayicon.pixmaps("red", {"number": "", "fill": 0.4})[3]
    assert ring_right(data, w, h) == (255, 0xFF, 0x7B, 0x63)
    assert ring_left(data, w, h)[0] == 255 and ring_left(data, w, h)[1:] != (0xFF, 0x7B, 0x63)  # the track, dimmed over the disc


def test_digits_drawn_in_centre():
    with_digits = trayicon.pixmaps("green", {"number": "30", "fill": 0.5})[3][2]
    blank = trayicon.pixmaps("green", {"number": "", "fill": 0.5})[3][2]
    assert with_digits != blank


def test_unknown_colour_falls_back_to_grey():
    assert trayicon.pixmaps("nope", TRAY)[0][2] == trayicon.pixmaps("grey", TRAY)[0][2]


def test_ring_sits_on_a_dark_disc_so_it_reads_on_a_light_panel_too():
    # Breeze Light's tray is near-white and the pastel ring alone washes out on it
    w, h, data = trayicon.pixmaps("green", {"number": "", "fill": 1.0})[3]
    a, r, g, b = px(data, w, w // 2 - 14, h // 2 - 14)
    assert a == 255 and r + g + b < 200


def test_save_png(tmp_path):
    p = tmp_path / "a.png"
    trayicon.save_png(p, "amber", {"number": "36", "fill": 0.85}, 64)
    assert p.read_bytes()[:4] == b"\x89PNG"
