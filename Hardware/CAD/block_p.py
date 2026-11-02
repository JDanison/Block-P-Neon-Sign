"""
    Filename: block_p.py
    Description:
        Parametric CAD model of the Block P sign (8 inch build). Running it rebuilds every
        printed part, checks the fit, and writes print files, STEP files and viewer meshes.

    Coordinates:
        x runs right and y runs up from the foot's lower left corner. z = 0 is the wall side
        and z = DEPTH is the front face. All sizes are mm.

    Run:
        .venv/Scripts/python block_p.py

    Sizes marked ASSUMED are estimates until the real parts are measured.
"""

import json
import pathlib

from wiring import build_route
from build123d import Axis, Box, Compound, Cylinder, Polygon, Pos, Plane, Rot, Solid, Sphere, Vector, extrude, export_step, export_stl, fillet

OUT = pathlib.Path(__file__).parent

# Locked shape, in marcher grid spots
UNIT = 12.6               # raised from 11.9 to open clearances
STEM_WIDEN = 10.0         # added to the stem, half on each side, the width of the gold edge
STEM_L = 2.5 - STEM_WIDEN / 2 / UNIT
STEM_R = 6.5 + STEM_WIDEN / 2 / UNIT
FOOT_L = -STEM_WIDEN / 2 / UNIT      # the foot grows by the same margin, staying centered on the stem
FOOT_R = 9 + STEM_WIDEN / 2 / UNIT
FOOT_T = (FOOT_R - FOOT_L) * 4 / 9   # keeps the drill chart's 9:4 foot proportion
SHAPE = [(FOOT_L, 0), (FOOT_R, 0), (FOOT_R, FOOT_T), (STEM_R, FOOT_T), (STEM_R, 13), (25.5, 13), (25.5, 31), (0, 31),
         (0, 27), (STEM_L, 27), (STEM_L, FOOT_T), (FOOT_L, FOOT_T)]

# Enclosure
DEPTH = 55.0              # set by the speakers' 45 mm width and 1.5 mm clearance
WALL = 3.0
FRONT = 3.0
FRONT_SKIN = 2.0          # no blind hole may come closer than this to the front face
COVER = 3.0
SPLIT_SHELL = 11 * UNIT   # where the front shell splits into two sections
SPLIT_COVER = 112.0       # covers split lower so they bridge the shell joint

# LED edge
LED_STEP = 10.0           # how far the LED channel sits in from the outline
LED_DEPTH = 13.0           # how far the channel runs back from the front face
LED_FLOOR = 2.0           # material between the channel and the rear cavity
DIFFUSER_WALL = 2.0
TONGUE = 4.0              # diffuser overlap onto the shell, glued
TONGUE_T = 1.2
FIT = 0.15
STRIP_W, STRIP_T = 10.0, 0.3      # ASSUMED standard WS2812B strip, confirm on yours
LED_SIZE, LED_H = 5.0, 1.6
LED_PITCH = 1000 / 60             # ASSUMED 60 LEDs per meter
STRIP_END = 9.0                   # bare wall left at each corner for the jumpers
STRIP_SEAM = 16.0                 # extra room at the two strip ends, so power wires can turn

# Waveshare 8DP-CAPLCD
PANEL_W, PANEL_H = 194.0, 119.0
PANEL_T = 5.0             # from Waveshare's drawing, 11 mm including the rear board
WINDOW_W, WINDOW_H = 188.0, 113.0
PICTURE_W, PICTURE_H = 172.82, 108.24
# The panel is rotated 180 degrees so its ports face down. Rear board positions are scaled
# from Waveshare's interface photo: u and v are mm from the panel's corner in that photo.
SCREEN_BOARD_Z = 45.0     # rear face of the screen's circuit board

# Other parts
SPK_L, SPK_W, SPK_T = 100.0, 45.0, 21.0  # from matching speakers, confirm on yours
SPK_HOLE_L, SPK_HOLE_W = 92.0, 36.0      # mounting hole spacing from your listing
SPK_EAR_Y0, SPK_EAR_Y1 = 2.0, 4.5        # ASSUMED, tab position back from the speaker face
SPK_CHIMNEY = 9.0                        # gap from the grille wall up to the speaker face
# Raspberry Pi 4B positions are from the official mechanical drawing, with the board
# corner at PI_X, PI_Y. The GPIO header faces up the sign and the USB ports face right.
PI_X, PI_Y = 128.0, 242.0
PI_L, PI_W, PI_BOARD_T = 85.0, 56.0, 1.4
PI_HOLE_X, PI_HOLE_Y = (3.5, 61.5), (3.5, 52.5)
# Geekworm N300 case. Thickness and spacers are published, the rest is from photos.
CASE_T = 16.0
CASE_X0, CASE_X1, CASE_Y0, CASE_Y1 = -2.5, 88.0, -2.5, 58.5   # ASSUMED, relative to the board
CASE_FIN = 5.0
CASE_PCB_Z = 7.0          # ASSUMED, case bottom to the underside of the board
CASE_TOP_T = 2.6
SPACER_H = 5.0            # brass spacers from the kit, added above the top cover
CONV_X, CONV_Y = 38.0, 245.0
CONV_L, CONV_W, CONV_T = 75.0, 41.0, 17.0   # ASSUMED, use the real converter
AUDIO_X, AUDIO_Y = 285.0, 238.0          # low end, at the speaker header
AUDIO_W, AUDIO_L, AUDIO_T = 23.5, 47.0, 14.6   # body, plus a USB plug. Confirm on yours
AUDIO_PLUG = 13.0
PERF_X, PERF_Y, PERF_S = 150.0, 308.0, 30.5
JACK_D = 12.0             # ASSUMED, listings say 11 to 12


def inset(points, d):
    """Offsets an axis-aligned counterclockwise outline inward by d."""
    n = len(points)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = points[i], points[(i + 1) % n]
        if y0 == y1:
            lines.append(("h", y0 + (d if x1 > x0 else -d)))
        else:
            lines.append(("v", x0 + (-d if y1 > y0 else d)))
    result = []
    for i in range(n):
        a, b = lines[i - 1], lines[i]
        x = a[1] if a[0] == "v" else b[1]
        y = a[1] if a[0] == "h" else b[1]
        result.append((x, y))
    return result


def prism(points, z0, z1):
    return Pos(0, 0, z0) * extrude(Polygon(*points, align=None), amount=z1 - z0)


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def cyl(x, y, d, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(d / 2, z1 - z0)


def union(parts):
    result = parts[0]
    for part in parts[1:]:
        result = result + part
    return result


O = [(x * UNIT, y * UNIT) for x, y in SHAPE]
W_TOTAL, H_TOTAL = 25.5 * UNIT, 31 * UNIT
SCREEN_X, SCREEN_Y = (STEM_L * UNIT + W_TOTAL) / 2, 22 * UNIT
BAND_Y = 13 * UNIT        # underside of the band below the screen
FOOT_W, FOOT_H = 9 * UNIT, 4 * UNIT
STEM_X0, STEM_X1 = STEM_L * UNIT, STEM_R * UNIT

PANEL_Z0 = DEPTH - FRONT - PANEL_T
PANEL_X0, PANEL_X1 = SCREEN_X - PANEL_W / 2, SCREEN_X + PANEL_W / 2
PANEL_Y0, PANEL_Y1 = SCREEN_Y - PANEL_H / 2, SCREEN_Y + PANEL_H / 2
CLAMP_T = 4.0

SPK_CENTERS = [143.0, 259.0]
SPK_Y0 = BAND_Y + WALL + SPK_CHIMNEY
SPK_Y1 = SPK_Y0 + SPK_T
SPK_Z0 = COVER + 1.5
SPK_Z1 = SPK_Z0 + SPK_W
SPK_ZC = (SPK_Z0 + SPK_Z1) / 2
SPK_REAR_Z = SPK_ZC - SPK_HOLE_W / 2

AUDIO_STRAP_XS = (AUDIO_X - 6.0, AUDIO_X + AUDIO_W + 4.5)
AUDIO_STRAP_Y = AUDIO_Y + 26.0

CLAMP_XS = (PANEL_X0 - 9.5, PANEL_X1 + 9.5)
CLAMP_TOP_Y = PANEL_Y1 + 6
CLAMP_BOTTOM_Y = PANEL_Y0 - 6
SPLICE_XS = (49.0, 64.5)
SPLICE_YS = (SPLIT_SHELL - 12, SPLIT_SHELL + 12)
SPLICE_BOSS = 5.0
SPLICE_Z1 = DEPTH - FRONT - SPLICE_BOSS

SCALE = UNIT / 11.9
SCREWS_UPPER = [(8 * SCALE, 361 * SCALE), (150 * SCALE, 361 * SCALE), (295 * SCALE, 361 * SCALE), (8.5, 346.5),
                (33, 307), (33, 238), (33, 175), (33, 119), (80, 119), (80, 155),
                (314.5, 317), (316.0, 243.5), (315.5, 169), (201, 169)]
SCREWS_LOWER = [(33, 104), (80, 104), (33, 57), (80, 57), (3.5, 8.5), (110, 8.5), (3.5, 42), (110, 42)]
KEYHOLES = [(75.0, 370.0), (276.0, 370.0)]
PI_Z0 = COVER
PI_BOARD_Z = PI_Z0 + CASE_PCB_Z + PI_BOARD_T   # top of the board
PI_BRACKET_Z = PI_Z0 + CASE_T + SPACER_H
PI_BRACKET_T = 3.0
PI_HOLES = [(PI_X + x, PI_Y + y) for x in PI_HOLE_X for y in PI_HOLE_Y]
PI_POSTS = [(PI_X - 9, PI_Y + 3.5), (PI_X - 9, PI_Y + 52.5), (PI_X + 61.5, PI_Y - 9), (PI_X + 61.5, PI_Y + 65)]
PERF_POSTS = [(PERF_X + dx, PERF_Y + dy) for dx in (3, PERF_S - 3) for dy in (3, PERF_S - 3)]


# Natural airflow: cool air in low, warm air out high. Slots stay clear of the LED channel.
VENT_W = 5.0
VENT_Z0, VENT_Z1 = 8.0, 34.0


def vent_slots():
    """Returns (position, wall) for every vent. Wall is top, right, left or under."""
    screw_x = [q[0] for q in SCREWS_UPPER if q[1] > H_TOTAL - 20]
    right_y = [q[1] for q in SCREWS_UPPER if q[0] > W_TOTAL - 12]
    left_y = [q[1] for q in SCREWS_UPPER if 28 < q[0] < 45]
    slots = {"top": [], "right_high": [], "right_low": [], "left": [], "under": [], "foot": [], "stem_left": [], "stem_right": []}
    x = 60.0
    while x < W_TOTAL - 20:
        if all(abs(x - c) > 8 for c in screw_x):
            slots["top"].append(x)
        x += 10
    y = BAND_Y + 12
    while y < H_TOTAL - 16:
        if all(abs(y - c) > 8 for c in right_y):
            slots["right_low" if y < 262 else "right_high"].append(y)
        y += 10
    y = 182.0
    while y < 330:
        if all(abs(y - c) > 8 for c in left_y):
            slots["left"].append(y)
        y += 10
    slots["under"] = [90.0, 95.0, 196.0, 206.0]
    slots["foot"] = [x for x in (18.0, 26.0, 34.0, 42.0, 72.0, 80.0, 88.0, 96.0)]
    lower = [q[1] for q in SCREWS_LOWER + SCREWS_UPPER]
    y = 62.0
    while y < 158:
        if abs(y - SPLIT_SHELL) > 8 and all(abs(y - c) > 8 for c in lower):
            slots["stem_left"].append(y)
            slots["stem_right"].append(y)
        y += 10
    return slots


def vent_cuts():
    cuts = []
    slots = vent_slots()
    half = VENT_W / 2
    for x in slots["top"]:
        cuts.append(box(x - half, x + half, H_TOTAL - WALL - 1, H_TOTAL + 1, VENT_Z0, VENT_Z1))
    for y in slots["right_low"] + slots["right_high"]:
        cuts.append(box(W_TOTAL - WALL - 1, W_TOTAL + 1, y - half, y + half, VENT_Z0, VENT_Z1))
    for y in slots["left"]:
        cuts.append(box(STEM_X0 - 1, STEM_X0 + WALL + 1, y - half, y + half, VENT_Z0, VENT_Z1))
    for y in slots["stem_left"]:
        cuts.append(box(STEM_X0 - 1, STEM_X0 + WALL + 1, y - half, y + half, VENT_Z0, VENT_Z1))
    for y in slots["stem_right"]:
        cuts.append(box(STEM_X1 - WALL - 1, STEM_X1 + 1, y - half, y + half, VENT_Z0, VENT_Z1))
    for x in slots["foot"]:
        cuts.append(box(x - half, x + half, -1, WALL + 1, VENT_Z0, VENT_Z1))
    for x in slots["under"]:
        cuts.append(box(x - 1.5, x + 1.5, BAND_Y - 1, BAND_Y + WALL + 1, 10, 36))
    return cuts


def vent_report():
    """Compares vent area with the area needed for natural airflow to carry the heat away."""
    slots = vent_slots()
    area = (VENT_Z1 - VENT_Z0) * VENT_W
    low = len(slots["right_low"]) + len(slots["foot"]) + len(slots["stem_left"]) + len(slots["stem_right"])
    inlet = low * area + len(slots["under"]) * 3 * 26
    outlet = (len(slots["top"]) + len(slots["right_high"]) + len(slots["left"])) * area
    effective = 1 / (1 / inlet ** 2 + 1 / outlet ** 2) ** 0.5 / 1e6
    heat, height = 13.0, 0.25      # W inside the cavity, and m of rise from inlets to outlets. The LEDs have their own channel
    rise = (heat / (1.2 * 1005 * 0.6 * effective * (2 * 9.8 * height / 300) ** 0.5)) ** (2 / 3)
    print(f"  {sum(len(v) for v in slots.values())} slots: {inlet:.0f} mm2 in, {outlet:.0f} mm2 out")
    print(f"  Estimated air temperature rise from airflow alone: {rise:.0f} C")


def front_shell():
    solid = prism(O, 0, DEPTH)
    solid -= prism(O, DEPTH - LED_DEPTH, DEPTH + 1) - prism(inset(O, LED_STEP), DEPTH - LED_DEPTH - 1, DEPTH + 2)
    recess = prism(O, DEPTH - LED_DEPTH - TONGUE, DEPTH - LED_DEPTH + 0.01)
    recess -= prism(inset(O, TONGUE_T + FIT), DEPTH - LED_DEPTH - TONGUE - 1, DEPTH)
    solid -= recess

    cavity = prism(inset(O, WALL), -1, DEPTH - LED_DEPTH - LED_FLOOR)
    cavity += prism(inset(O, LED_STEP + 2), DEPTH - LED_DEPTH - LED_FLOOR - 0.1, DEPTH - FRONT)

    keep = [cyl(x, y, 8, COVER, DEPTH) for x, y in SCREWS_UPPER + SCREWS_LOWER]
    keep += [cyl(x, y, 8, PANEL_Z0, DEPTH) for x in CLAMP_XS for y in (CLAMP_TOP_Y, CLAMP_BOTTOM_Y)]
    keep += [cyl(x, y, 7, SPLICE_Z1, DEPTH) for x in SPLICE_XS for y in SPLICE_YS]
    for cx in SPK_CENTERS:
        for x in (cx - SPK_HOLE_L / 2, cx + SPK_HOLE_L / 2):
            # Rear tabs screw down onto posts. Front tabs hook under pads on the front wall.
            keep.append(Pos(x, BAND_Y + WALL / 2 + SPK_CHIMNEY / 2, SPK_REAR_Z) * Rot(90, 0, 0) * Cylinder(4, SPK_CHIMNEY + WALL))
            keep.append(box(x - 5, x + 5, SPK_Y0 + SPK_EAR_Y1 + 0.4, SPK_Y0 + SPK_EAR_Y1 + 3.4, DEPTH - FRONT - 9, DEPTH))
    cavity -= union(keep)
    shell = solid - cavity

    holes = [cyl(x, y, 2.5, COVER - 1, COVER + 12) for x, y in SCREWS_UPPER + SCREWS_LOWER]
    holes += [cyl(x, y, 2.5, PANEL_Z0 - 1, DEPTH - FRONT_SKIN) for x in CLAMP_XS for y in (CLAMP_TOP_Y, CLAMP_BOTTOM_Y)]
    holes += [cyl(x, y, 2.5, SPLICE_Z1 - 1, DEPTH - FRONT_SKIN) for x in SPLICE_XS for y in SPLICE_YS]

    for cx in SPK_CENTERS:
        for x in (cx - SPK_HOLE_L / 2, cx + SPK_HOLE_L / 2):
            holes.append(Pos(x, SPK_Y0 - 4, SPK_REAR_Z) * Rot(90, 0, 0) * Cylinder(1.25, 8.2))

    holes.append(box(SCREEN_X - WINDOW_W / 2, SCREEN_X + WINDOW_W / 2, SCREEN_Y - WINDOW_H / 2,
                     SCREEN_Y + WINDOW_H / 2, DEPTH - FRONT - 1, DEPTH + 1))

    # Speaker grilles through the underside of the band
    for cx in SPK_CENTERS:
        for i in range(11):
            x = cx - 40 + i * 8
            holes.append(box(x - 1.7, x + 1.7, BAND_Y - 1, BAND_Y + WALL + 1, SPK_ZC - 15, SPK_ZC + 15))

    holes += vent_cuts()

    # Power jack through the bottom of the foot
    holes.append(Pos(FOOT_W / 2, 0, 21) * Rot(90, 0, 0) * Cylinder(JACK_D / 2, 14))

    # LED wire holes at the strip's start and end
    holes.append(Pos(STEM_X1 - LED_STEP + 5, BAND_Y + LED_STEP, DEPTH - 2.5 - STRIP_W / 2) * Rot(90, 0, 0) * Cylinder(3, 8))
    holes.append(Pos(STEM_X1 - LED_STEP, BAND_Y + LED_STEP - 5, DEPTH - 2.5 - STRIP_W / 2) * Rot(0, 90, 0) * Cylinder(3, 8))
    return shell - union(holes)


def diffuser():
    ring = prism(O, DEPTH - DIFFUSER_WALL, DEPTH) - prism(inset(O, LED_STEP - FIT), DEPTH - 3, DEPTH + 1)
    ring += prism(O, DEPTH - LED_DEPTH, DEPTH - DIFFUSER_WALL + 0.01) - prism(inset(O, DIFFUSER_WALL), DEPTH - LED_DEPTH - 1, DEPTH)
    ring += prism(O, DEPTH - LED_DEPTH - TONGUE, DEPTH - LED_DEPTH + 0.01) - prism(inset(O, TONGUE_T), DEPTH - LED_DEPTH - TONGUE - 1, DEPTH)
    return ring


# Every zip-tie clip: what it holds, position, and whether the tie passes along x.
# A tie crosses its wire, so wires running along y use along_x=True.
ZIP_CLIPS = [
    ("Converter, lower tie", CONV_X + CONV_L / 2, CONV_Y - 7, False),
    ("Converter, upper tie", CONV_X + CONV_L / 2, CONV_Y + CONV_W + 7, False),
    ("12V in, stem top", 56.7, 190, True),
    ("12V in, stem middle", 56.7, 125, True),
    ("12V in, stem bottom", 56.7, 60, True),
    ("5V junction", 118, 226, True),
    ("LED far end power", 88, 223, False),
    ("LED start power", 112, 212, True),
    ("Speaker leads", 245, 204, False),
    ("USB to dongle", AUDIO_X + AUDIO_W / 2, 330, True),
]


def zip_anchor(x, y, along_x=True):
    block = box(x - 6, x + 6, y - 4, y + 4, COVER, COVER + 5) if along_x else box(x - 4, x + 4, y - 6, y + 6, COVER, COVER + 5)
    slot = box(x - 7, x + 7, y - 2.5, y + 2.5, COVER, COVER + 2) if along_x else box(x - 2.5, x + 2.5, y - 7, y + 7, COVER, COVER + 2)
    return block - slot


def cradle(x0, x1, y0, y1, height):
    """Corner stops that locate a part, which a zip tie then holds down."""
    parts = []
    for cx, sx in ((x0, -1), (x1, 1)):
        for cy, sy in ((y0, -1), (y1, 1)):
            parts.append(box(min(cx, cx + 2 * sx), max(cx, cx + 2 * sx), min(cy, cy - 8 * sy), max(cy, cy - 8 * sy) + 0, COVER, COVER + height))
            parts.append(box(min(cx, cx - 8 * sx), max(cx, cx - 8 * sx), min(cy, cy + 2 * sy), max(cy, cy + 2 * sy), COVER, COVER + height))
    return union(parts)


def back_covers():
    plate = prism(inset(O, WALL + 0.2), 0, COVER)
    add = []
    cut = []

    for x, y in KEYHOLES:
        add.append(box(x - 13, x + 13, y - 17, y + 16, COVER, COVER + 6))
        cut.append(box(x - 10, x + 10, y - 14, y + 13, COVER, COVER + 3.5))
        cut.append(cyl(x, y - 6, 9.5, -1, COVER + 1))
        cut.append(box(x - 2.5, x + 2.5, y - 6, y + 7, -1, COVER + 1))
        cut.append(cyl(x, y + 7, 5, -1, COVER + 1))

    add += [cyl(x, y, 8, COVER, PI_BRACKET_Z) for x, y in PI_POSTS]
    add.append(cradle(PI_X + CASE_X0 - 0.2, PI_X + CASE_X1 + 0.2, PI_Y + CASE_Y0 - 0.2, PI_Y + CASE_Y1 + 0.2, 4))
    add += [cyl(x, y, 6, COVER, COVER + 8) for x, y in PERF_POSTS]
    add.append(cradle(CONV_X, CONV_X + CONV_L, CONV_Y, CONV_Y + CONV_W, 8))
    # USB audio dongle: a low cradle, with a screwed strap across the top
    ax0, ax1, ay1 = AUDIO_X - 0.2, AUDIO_X + AUDIO_W + 0.2, AUDIO_Y + AUDIO_L
    add.append(box(ax0 - 2, ax0, AUDIO_Y + 4, ay1 + 2, COVER, COVER + 8))
    add.append(box(ax1, ax1 + 2, AUDIO_Y + 4, ay1 + 2, COVER, COVER + 8))
    add.append(box(ax0, AUDIO_X + 5, ay1 + 0.2, ay1 + 2, COVER, COVER + 8))
    add.append(box(AUDIO_X + AUDIO_W - 5, ax1, ay1 + 0.2, ay1 + 2, COVER, COVER + 8))
    add += [cyl(x, AUDIO_STRAP_Y, 8, COVER, COVER + AUDIO_T + 0.3) for x in AUDIO_STRAP_XS]

    add += [zip_anchor(x, y, along_x) for _, x, y, along_x in ZIP_CLIPS]

    cut += [cyl(x, y, 2.5, COVER + 2, PI_BRACKET_Z + 1) for x, y in PI_POSTS]
    cut += [cyl(x, y, 2.2, COVER + 2, COVER + 9) for x, y in PERF_POSTS]
    cut += [cyl(x, AUDIO_STRAP_Y, 2.5, COVER + 2, COVER + AUDIO_T + 1) for x in AUDIO_STRAP_XS]
    for x, y in SCREWS_UPPER + SCREWS_LOWER:
        cut.append(cyl(x, y, 3.4, -1, COVER + 1))
        cut.append(cyl(x, y, 6.4, -1, 1.8))
    for i in range(6):
        y = PI_Y + 10 + i * 7.5
        cut.append(box(PI_X + 12, PI_X + 70, y - 1.5, y + 1.5, -1, COVER + 1))

    whole = plate + union(add) - union(cut)
    upper = whole & box(-10, W_TOTAL + 10, SPLIT_COVER + FIT, H_TOTAL + 10, -1, DEPTH)
    lower = whole & box(-10, W_TOTAL + 10, -10, SPLIT_COVER - FIT, -1, DEPTH)
    return upper, lower


JUNCTION = (110.0, 126.0, 221.0, 231.0)
CONV_GLANDS = (CONV_X + 14, CONV_X + 60)
CONV_GLAND_Z = COVER + 8.5


def pi_brackets():
    """The case has no mounting holes underneath, so these hold it by the top cover screw positions."""
    z0, z1 = PI_BRACKET_Z, PI_BRACKET_Z + PI_BRACKET_T
    hx0, hx1 = PI_X + PI_HOLE_X[0], PI_X + PI_HOLE_X[1]
    hy0, hy1 = PI_Y + PI_HOLE_Y[0], PI_Y + PI_HOLE_Y[1]
    left = box(hx0 - 4, hx0 + 4, hy0 - 5, hy1 + 5, z0, z1)
    for y in (hy0, hy1):
        left += box(PI_X - 14, hx0, y - 5, y + 5, z0, z1)
    for x, y in ((hx0, hy0), (hx0, hy1), (PI_POSTS[0][0], hy0), (PI_POSTS[1][0], hy1)):
        left -= cyl(x, y, 3.4 if x < hx0 else 2.9, z0 - 1, z1 + 1)
    low = box(hx1 - 5, hx1 + 5, PI_POSTS[2][1] - 5, hy0 + 5, z0, z1)
    high = box(hx1 - 5, hx1 + 3, hy1 - 5, PI_POSTS[3][1] + 5, z0, z1)
    low -= cyl(hx1, PI_POSTS[2][1], 3.4, z0 - 1, z1 + 1) + cyl(hx1, hy0, 2.9, z0 - 1, z1 + 1)
    high -= cyl(hx1, PI_POSTS[3][1], 3.4, z0 - 1, z1 + 1) + cyl(hx1, hy1, 2.9, z0 - 1, z1 + 1)
    return left, low, high


def pi_case_bottom():
    x0, x1, y0, y1 = PI_X + CASE_X0, PI_X + CASE_X1, PI_Y + CASE_Y0, PI_Y + CASE_Y1
    z0, z1 = PI_Z0, PI_Z0 + CASE_T - CASE_TOP_T
    part = box(x0, x1, y0, y1, z0, z1)
    part = fillet(part.edges().filter_by(Axis.Z), 3.5)
    part -= box(x0 + 2, x1 + 1, y0 + 2, y1 - 2, z0 + CASE_FIN + 1, z1 + 1)
    fins = []
    x = x0 + 8
    while x < x1 - 6:
        fins.append(box(x, x + 2.2, y0 + 1.5, y1 - 1.5, z0 - 1, z0 + CASE_FIN - 1))
        x += 4.6
    y = y0 + 8
    while y < y1 - 6:
        fins.append(box(x0 + 13, x1 - 12, y, y + 2.2, z0 - 1, z0 + CASE_FIN - 1))
        y += 5
    part -= union(fins)
    # Connector window along the HDMI side, cable exits and microSD slot
    part -= box(PI_X + 3, PI_X + 62, y0 - 1, y0 + 3, PI_BOARD_Z - 1.5, z1 + 1)
    part -= box(x0 - 1, x0 + 3, PI_Y + 8, PI_Y + 48, PI_Z0 + CASE_PCB_Z - 3, PI_Z0 + CASE_PCB_Z + 2)
    return part


def pi_case_top():
    x0, x1, y0, y1 = PI_X + CASE_X0, PI_X + CASE_X1, PI_Y + CASE_Y0, PI_Y + CASE_Y1
    z1 = PI_Z0 + CASE_T
    part = box(x0, x1, y0, y1, z1 - CASE_TOP_T, z1)
    part = fillet(part.edges().filter_by(Axis.Z), 3.5)
    for yc, half in ((9, 8.5), (27, 8.5), (45.75, 8.5)):
        part -= box(PI_X + 65, x1 + 1, PI_Y + yc - half, PI_Y + yc + half, z1 - CASE_TOP_T - 1, z1 + 1)
    part -= box(PI_X + 7, PI_X + 58, PI_Y + 49.8, PI_Y + 55.2, z1 - CASE_TOP_T - 1, z1 + 1)
    part -= box(PI_X + 0.5, PI_X + 5.5, PI_Y + 14.5, PI_Y + 40.5, z1 - CASE_TOP_T - 1, z1 + 1)
    part -= box(PI_X + 44.5, PI_X + 48.5, PI_Y + 3, PI_Y + 15.5, z1 - CASE_TOP_T - 1, z1 + 1)
    part -= box(PI_X + 49.5, PI_X + 58.5, PI_Y + CASE_Y0 - 1, PI_Y + 13, z1 - CASE_TOP_T - 1, z1 - CASE_TOP_T + 1.2)   # audio jack relief
    part -= cyl(PI_X + 28, PI_Y + 25, 30, z1 - 0.6, z1 + 1) - cyl(PI_X + 28, PI_Y + 25, 28, z1 - 1, z1 + 1)
    for x, y in PI_HOLES:
        part -= cyl(x, y, 2.9, z1 - CASE_TOP_T - 1, z1 + 1)
    return part


def pi_board():
    z0 = PI_BOARD_Z - PI_BOARD_T
    part = box(PI_X, PI_X + PI_L, PI_Y, PI_Y + PI_W, z0, PI_BOARD_Z)
    part = fillet(part.edges().filter_by(Axis.Z), 3)
    part += box(PI_X + 28, PI_X + 43, PI_Y + 17, PI_Y + 32, PI_BOARD_Z, PI_BOARD_Z + 2.4)
    for x, y in PI_HOLES:
        part -= cyl(x, y, 2.7, z0 - 1, PI_BOARD_Z + 1)
    return part


def pi_connectors():
    t = PI_BOARD_Z
    x, y = PI_X, PI_Y
    parts = []
    for yc in (9.0, 27.0):                                  # USB stacks
        stack = box(x + 69, x + 87, y + yc - 6.6, y + yc + 6.6, t, t + 16)
        for z in (t + 4, t + 12):
            stack -= box(x + 74, x + 88, y + yc - 6, y + yc + 6, z - 2.6, z + 2.6)
        parts.append(stack)
    parts.append(box(x + 66, x + 87, y + 45.75 - 8, y + 45.75 + 8, t, t + 13.5))   # Ethernet
    parts.append(box(x + 7, x + 58, y + 50.2, y + 54.8, t, t + 8.5))                # GPIO header
    usb_c = box(x + 11.2 - 4.5, x + 11.2 + 4.5, y - 1, y + 6, t, t + 3.2)
    parts.append(usb_c - box(x + 11.2 - 3.7, x + 11.2 + 3.7, y - 2, y + 5, t + 0.5, t + 2.7))
    for xc in (26.0, 39.5):                                 # micro-HDMI
        hdmi = box(x + xc - 3.3, x + xc + 3.3, y - 1, y + 7, t, t + 3)
        parts.append(hdmi - box(x + xc - 2.6, x + xc + 2.6, y - 2, y + 6, t + 0.5, t + 2.5))
    parts.append(box(x + 50.5, x + 57.5, y, y + 12, t, t + 6))                      # audio jack
    parts.append(Pos(x + 54, y - 1, t + 3) * Rot(90, 0, 0) * Cylinder(3, 3))
    parts.append(box(x + 1, x + 5, y + 15, y + 40, t, t + 5.5))                     # display connector
    parts.append(box(x + 45, x + 48, y + 3.5, y + 15, t, t + 5.5))                  # camera connector
    parts.append(box(x + 2, x + 14, y + 22, y + 34, PI_BOARD_Z - PI_BOARD_T - 0.9, PI_BOARD_Z - PI_BOARD_T))  # microSD
    return union(parts)


def pi_spacers():
    parts = []
    for px, py in PI_HOLES:
        parts.append(cyl(px, py, 5, PI_BOARD_Z, PI_Z0 + CASE_T - CASE_TOP_T))
        parts.append(cyl(px, py, 5, PI_Z0 + CASE_T, PI_BRACKET_Z))
        parts.append(cyl(px, py, 2.5, PI_Z0 + CASE_T - CASE_TOP_T, PI_Z0 + CASE_T))
    return union(parts)


def usb_a_plug(x0, y, z):
    """Plugged-in USB-A: metal collar, molded body and strain relief, running in +x."""
    collar = box(x0, x0 + 5, y - 6.2, y + 6.2, z - 2.6, z + 2.6)
    body = box(x0 + 5, x0 + 24, y - 7, y + 7, z - 3.9, z + 3.9)
    body = fillet(body.edges().filter_by(Axis.X), 1.5)
    relief = Pos(x0 + 29, y, z) * Rot(0, 90, 0) * Cylinder(2.8, 10)
    return collar + body + relief


def cable_plugs():
    """Plugs on the Pi: two USB-A in the lower stack, USB-C power and the micro-HDMI ribbon head."""
    t = PI_BOARD_Z
    x, y = PI_X, PI_Y
    parts = [usb_a_plug(x + 87, y + 9, t + 4), usb_a_plug(x + 87, y + 9, t + 12)]
    xc = x + 11.2
    usb_c = box(xc - 5.5, xc + 5.5, y - 22, y - 3, t - 2.5, t + 5.5)
    usb_c = fillet(usb_c.edges().filter_by(Axis.Y), 2)
    parts.append(usb_c + Pos(xc, y - 26, t + 1.5) * Rot(90, 0, 0) * Cylinder(2.4, 8))
    parts.append(box(x + 26 - 5.5, x + 26 + 5.5, y - 11, y - 3, t - 1.5, t + 3.5))
    parts.append(box(x + 26 - 4.5, x + 26 + 4.5, y - 18, y - 11, t - 0.1, t + 1.1))
    return union(parts)


def audio_strap():
    z0 = COVER + AUDIO_T + 0.3
    bar = box(AUDIO_STRAP_XS[0] - 6, AUDIO_STRAP_XS[1] + 4.2, AUDIO_STRAP_Y - 6, AUDIO_STRAP_Y + 6, z0, z0 + 3)
    for x in AUDIO_STRAP_XS:
        bar -= cyl(x, AUDIO_STRAP_Y, 3.4, z0 - 1, z0 + 4)
    return bar


def speaker(cx, cable_side):
    """Speaker from product photos: notched body, corner tabs and two 40 mm drivers."""
    n, hl, hw = 9.0, SPK_L / 2, SPK_W / 2
    outline = [(-hl + n, -hw), (hl - n, -hw), (hl - n, -hw + n), (hl, -hw + n), (hl, hw - n), (hl - n, hw - n),
               (hl - n, hw), (-hl + n, hw), (-hl + n, hw - n), (-hl, hw - n), (-hl, -hw + n), (-hl + n, -hw + n)]
    body = prism(outline, 0, 15) + box(-hl, hl, -hw + 5, hw - 5, 15, SPK_T)
    for sx in (-1, 1):
        body -= cyl(sx * 24, 0, 40, -1, 2.2)
        body += cyl(sx * 24, 0, 37, 2, 3)
        for sy in (-1, 1):
            x, y = sx * SPK_HOLE_L / 2, sy * SPK_HOLE_W / 2
            ear = cyl(x, y, 8, SPK_EAR_Y0, SPK_EAR_Y1) + box(min(x, sx * (hl - n)), max(x, sx * (hl - n)), y - 3, y + 3, SPK_EAR_Y0, SPK_EAR_Y1)
            body += ear - cyl(x, y, 3.4, SPK_EAR_Y0 - 1, SPK_EAR_Y1 + 1)
    body += cyl(-24, 0, 25, 1.4, 2.2)
    body += Pos(24, 0, 10.8) * Sphere(10.2)
    body += Pos(cable_side * (hl + 0.5), 9 * cable_side, 11) * Rot(0, 90, 0) * Cylinder(1.6, 1)
    return Pos(cx, SPK_Y0, SPK_ZC) * Rot(-90, 0, 0) * body


def audio_dongle():
    """USB dongle from product photos: rounded case, USB-A plug and 4-pin speaker header."""
    x0, x1 = AUDIO_X, AUDIO_X + AUDIO_W
    y0, y1 = AUDIO_Y, AUDIO_Y + AUDIO_L
    z0, z1 = COVER, COVER + AUDIO_T
    case = box(x0, x1, y0, y1, z0, z1)
    case = fillet(case.edges().filter_by(Axis.Y), 2.5)
    case -= box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, (z0 + z1) / 2 - 0.2, (z0 + z1) / 2 + 0.2) - box(x0 + 0.6, x1 - 0.6, y0 - 2, y1 + 2, z0, z1)
    xc, zc = (x0 + x1) / 2, (z0 + z1) / 2
    case -= box(xc - 5.5, xc + 5.5, y0 - 1, y0 + 6, zc - 3, zc + 3)
    plug = box(xc - 6, xc + 6, y1, y1 + AUDIO_PLUG, zc - 2.25, zc + 2.25)
    plug -= box(xc - 5.2, xc + 5.2, y1 + 3, y1 + AUDIO_PLUG + 1, zc - 1.7, zc + 1.7)
    return case + plug


def screen_clip(x, y):
    """Corner clip. Clips replace the full-width bars, which blocked the screen's cables."""
    toward_center = 1 if x < SCREEN_X else -1
    x0, x1 = sorted((x - 7 * toward_center, x + 26 * toward_center))
    bar = box(x0, x1, y - 8, y + 8, PANEL_Z0 - CLAMP_T, PANEL_Z0)
    return bar - cyl(x, y, 3.4, PANEL_Z0 - CLAMP_T - 1, PANEL_Z0 + 1)


def screen_uv(u, v):
    return PANEL_X0 + u, PANEL_Y0 + v


def screen_board():
    x0, y0 = screen_uv(40.9, 28.3)
    x1, y1 = screen_uv(150.4, 101.3)
    z0, z1 = SCREEN_BOARD_Z, SCREEN_BOARD_Z + 1.6
    board = box(x0, x1, y0, y1, z0, z1)
    a0, a1 = screen_uv(40, 74.6), screen_uv(53.3, 91.7)
    board -= box(a0[0], a1[0], a0[1], a1[1], z0 - 1, z1 + 1)
    n0, n1 = screen_uv(73, 27), screen_uv(134, 34)
    board -= box(n0[0], n1[0], n0[1], n1[1], z0 - 1, z1 + 1)
    b0, b1 = screen_uv(135.5, 43), screen_uv(151, 78)
    board -= box(b0[0], b1[0], b0[1], b1[1], z0 - 1, z1 + 1)
    for u, v in ((45, 32), (146.5, 32), (45, 98), (146.5, 98), (77.5, 39.5), (136, 39.5), (77.5, 89), (136, 89)):
        x, y = screen_uv(u, v)
        board -= cyl(x, y, 2.8, z0 - 1, z1 + 1)
    return board


def screen_ports():
    z1 = SCREEN_BOARD_Z
    parts = []
    # HDMI, power USB-C, touch USB-C, audio jack, chip, speaker and button headers, switch
    x, y = screen_uv(108.5, 34.4)
    hdmi = box(x - 7.6, x + 7.6, y, y + 11, z1 - 3.6, z1)
    parts.append(hdmi - box(x - 6.9, x + 6.9, y - 1, y + 10, z1 - 3, z1 - 0.6))
    x, y = screen_uv(129.7, 35)
    usb = box(x - 4.5, x + 4.5, y, y + 7.5, z1 - 3.2, z1)
    parts.append(usb - box(x - 3.7, x + 3.7, y - 1, y + 6.5, z1 - 2.7, z1 - 0.5))
    x, y = screen_uv(53.3, 84.4)
    usb = box(x, x + 7.5, y - 4.5, y + 4.5, z1 - 3.2, z1)
    parts.append(usb - box(x - 1, x + 6.5, y - 3.7, y + 3.7, z1 - 2.7, z1 - 0.5))
    x, y = screen_uv(86.5, 34.5)
    parts.append(box(x - 3.5, x + 3.5, y, y + 12, z1 - 5.5, z1))
    x, y = screen_uv(68, 67)
    parts.append(box(x - 7.5, x + 7.5, y - 7.5, y + 7.5, z1 - 1.4, z1))
    for u in (90, 102):
        x, y = screen_uv(u, 98)
        parts.append(box(x - 4, x + 4, y - 3, y + 3, z1 - 3, z1))
    return union(parts)


def screen_ribbon():
    x0, y0 = screen_uv(135, 43)
    x1, y1 = screen_uv(150, 88)
    flat = box(x0, x1, y0, y1, PANEL_Z0 - 0.3, PANEL_Z0)
    c0, c1 = screen_uv(136.5, 78), screen_uv(148.5, 86)
    return flat + box(c0[0], c1[0], c0[1], c1[1], SCREEN_BOARD_Z - 2.4, SCREEN_BOARD_Z)


def screen_plugs():
    """HDMI head, power USB-C and a right-angle touch USB-C, all lying flat behind the panel."""
    zc = SCREEN_BOARD_Z - 1.8
    parts = []
    x, y = screen_uv(108.5, 34.4)
    head = box(x - 6.7, x + 6.7, y - 4, y + 8, zc - 1.1, zc + 1.1)
    head += box(x - 8, x + 8, y - 22, y - 4, zc - 3.5, zc + 1.7)
    parts.append(head)
    x, y = screen_uv(129.7, 35)
    collar = box(x - 3.6, x + 3.6, y - 4, y + 6, zc - 0.7, zc + 1.1)
    body = box(x - 5.5, x + 5.5, y - 22, y - 4, zc - 3.6, zc + 1.7)
    parts.append(collar + fillet(body.edges().filter_by(Axis.Y), 2) + Pos(x, y - 26, zc) * Rot(90, 0, 0) * Cylinder(2.4, 8))
    x, y = screen_uv(53.3, 84.4)
    collar = box(x - 4, x + 6, y - 3.6, y + 3.6, zc - 0.7, zc + 1.1)
    body = box(x - 14, x - 4, y - 6, y + 10, zc - 3.6, zc + 1.7)
    parts.append(collar + body + Pos(x - 9, y + 13, zc) * Rot(90, 0, 0) * Cylinder(1.7, 6))
    return union(parts)


def stem_splice():
    plate = box(44.5, 69.0, SPLIT_SHELL - 20, SPLIT_SHELL + 20, SPLICE_Z1 - 4, SPLICE_Z1)
    for x in SPLICE_XS:
        for y in SPLICE_YS:
            plate -= cyl(x, y, 3.4, SPLICE_Z1 - 5, SPLICE_Z1 + 1)
    return plate


def usb_socket():
    xc, zc = AUDIO_X + AUDIO_W / 2, COVER + AUDIO_T / 2
    y0 = AUDIO_Y + AUDIO_L + 2.4
    body = box(xc - 8.5, xc + 8.5, y0, y0 + 28, zc - 5.3, zc + 5.3)
    body = fillet(body.edges().filter_by(Axis.Y), 2)
    body -= box(xc - 6.2, xc + 6.2, y0 - 1, y0 + AUDIO_PLUG, zc - 2.4, zc + 2.4)
    return body + Pos(xc, y0 + 31, zc) * Rot(90, 0, 0) * Cylinder(3, 7)


def speaker_plug():
    """4-pin JST housing, seated in the dongle's header."""
    xc, zc = AUDIO_X + AUDIO_W / 2, COVER + 7.3
    y0, y1 = AUDIO_Y - 8, AUDIO_Y + 6
    part = box(xc - 5.2, xc + 5.2, y0, y1, zc - 2.7, zc + 2.7)
    for i in range(4):
        x = xc - 3 + i * 2
        part -= box(x - 0.6, x + 0.6, y0 - 1, y0 + 4, zc - 1.2, zc + 1.2)
    return part


def power_jack():
    """Threaded barrel jack, with the nut and solder tabs inside the foot."""
    x, z = FOOT_W / 2, 21
    body = Pos(x, 6, z) * Rot(90, 0, 0) * Cylinder(JACK_D / 2 - 0.2, 12)
    nut = Pos(x, WALL + 1.5, z) * Rot(90, 0, 0) * Cylinder(8, 3)
    back = Pos(x, 14, z) * Rot(90, 0, 0) * Cylinder(4.5, 6)
    tab1 = box(x - 3.5, x - 2.5, 16, 22, z - 2, z + 2)
    tab2 = box(x + 2.5, x + 3.5, 16, 22, z - 2, z + 2)
    return body + nut + back + tab1 + tab2


def level_shifter():
    """Perfboard with the DIP-14 chip, resistor and capacitor."""
    z = COVER + 8
    board = box(PERF_X, PERF_X + PERF_S, PERF_Y, PERF_Y + PERF_S, z, z + 1.6)
    for x, y in PERF_POSTS:
        board -= cyl(x, y, 2.9, z - 1, z + 3)
    chip = box(PERF_X + 7, PERF_X + 14, PERF_Y + 8, PERF_Y + 27, z + 1.6, z + 5.6)
    resistor = Pos(PERF_X + 20, PERF_Y + 10, z + 3) * Rot(90, 0, 0) * Cylinder(1.25, 6.5)
    cap = cyl(PERF_X + 21, PERF_Y + 20, 8, z + 1.6, z + 13)
    return board, chip + resistor + cap


def converter():
    """Sealed converter: finned case, mounting ears and cable stubs."""
    x0, x1, y0, y1 = CONV_X, CONV_X + CONV_L, CONV_Y, CONV_Y + CONV_W
    z0, z1 = COVER, COVER + CONV_T
    part = box(x0 + 6, x1 - 6, y0, y1, z0, z1)
    part = fillet(part.edges().filter_by(Axis.X), 2)
    for i in range(7):
        y = y0 + 5 + i * 5.2
        part -= box(x0 + 12, x1 - 12, y - 0.8, y + 0.8, z1 - 1.4, z1 + 1)
    part += box(x0, x1, y0 + 3, y1 - 3, z0, z0 + 2.5)
    for x in CONV_GLANDS:
        part += Pos(x, y0 - 2.5, CONV_GLAND_Z) * Rot(90, 0, 0) * Cylinder(3, 5)
    for x in (x0 + 3, x1 - 3):
        part -= cyl(x, (y0 + y1) / 2, 3.4, z0 - 1, z0 + 4)
    return part


def stand_in_parts():
    shifter = level_shifter()
    items = {
        "Screen": box(PANEL_X0, PANEL_X1, PANEL_Y0, PANEL_Y1, PANEL_Z0, PANEL_Z0 + PANEL_T),
        "Screen board": screen_board(),
        "Screen ports": screen_ports(),
        "Screen ribbon": screen_ribbon(),
        "Screen plugs": screen_plugs(),
        "Pi case bottom": pi_case_bottom(),
        "Pi case top": pi_case_top(),
        "Pi board": pi_board(),
        "Pi connectors": pi_connectors(),
        "Pi brass spacers": pi_spacers(),
        "Cable plugs": cable_plugs(),
        "Converter": converter(),
        "USB audio dongle": audio_dongle(),
        "Speaker plug": speaker_plug(),
        "USB cable socket": usb_socket(),
        "Level shifter board": shifter[0],
        "Level shifter parts": shifter[1],
        "5V junction": box(JUNCTION[0], JUNCTION[1], JUNCTION[2], JUNCTION[3], COVER + 5.5, COVER + 10),
        "Power jack": power_jack(),
        "Speaker left": speaker(SPK_CENTERS[0], 1),
        "Speaker right": speaker(SPK_CENTERS[1], -1),
    }
    return items


def led_runs():
    """One strip section per straight wall, stopping short of each corner for the jumpers."""
    wall = inset(O, LED_STEP)
    n = len(wall)
    start = next(i for i, q in enumerate(O) if q == (STEM_R * UNIT, 13 * UNIT))
    runs = []
    for k in range(n):
        i = (start + k) % n
        (x0, y0), (x1, y1) = wall[i], wall[(i + 1) % n]
        length = abs(x1 - x0) + abs(y1 - y0)
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        nx, ny = uy, -ux                     # points outward from the wall
        runs.append((x0, y0, ux, uy, nx, ny, length))
    return runs


def run_layout(index, total, length):
    """Offset, LED count and span for one strip section."""
    before = STRIP_END + (STRIP_SEAM if index == 0 else 0)
    after = STRIP_END + (STRIP_SEAM if index == total - 1 else 0)
    leds = max(1, int((length - before - after) // LED_PITCH))
    span = leds * LED_PITCH
    return before + (length - before - after - span) / 2, leds, span


def led_ends():
    """First and last point of each strip section, with its outward normal."""
    result = []
    runs = led_runs()
    for index, (x0, y0, ux, uy, nx, ny, length) in enumerate(runs):
        a, leds, span = run_layout(index, len(runs), length)
        z = DEPTH - 2.5 - STRIP_W / 2
        lift = STRIP_T + 0.6
        result.append(((x0 + ux * a + nx * lift, y0 + uy * a + ny * lift, z),
                       (x0 + ux * (a + span) + nx * lift, y0 + uy * (a + span) + ny * lift, z), (ux, uy, 0), (nx, ny, 0)))
    return result


def led_jumpers():
    ends = led_ends()
    runs = led_runs()
    routes = []
    z_axis = (0, 0, 1)
    for i in range(len(ends) - 1):
        a, b = ends[i], ends[i + 1]
        cx, cy = runs[i + 1][:2]
        lift = 1.0
        corner = (cx + (a[3][0] + b[3][0]) * lift, cy + (a[3][1] + b[3][1]) * lift, a[0][2])
        routes.append(build_route(dict(
            name=f"LED corner {i + 1}", colors=["#d9342b", "#2fae5e", "#1b1b1b"], od=1.2, bend=3.5, kind="Jumper wire", pitch=3.2, lead=0.2,
            start=(a[1], a[2], z_axis), end=(b[0], tuple(-c for c in b[2]), z_axis), via=[corner], check=False)))
    return routes


def led_strip():
    """Returns the strip boards, the LED chips and the jumper paths between sections."""
    z = DEPTH - 2.5 - STRIP_W / 2
    boards, chips = [], []
    ends = []
    count = 0
    runs = led_runs()
    for index, (x0, y0, ux, uy, nx, ny, length) in enumerate(runs):
        a, leds, span = run_layout(index, len(runs), length)
        p0 = (x0 + ux * a, y0 + uy * a)
        p1 = (x0 + ux * (a + span), y0 + uy * (a + span))
        cx, cy = (p0[0] + p1[0]) / 2 + nx * STRIP_T / 2, (p0[1] + p1[1]) / 2 + ny * STRIP_T / 2
        if abs(ux) > 0.5:
            boards.append(box(cx - span / 2, cx + span / 2, cy - STRIP_T / 2, cy + STRIP_T / 2, z - STRIP_W / 2, z + STRIP_W / 2))
        else:
            boards.append(box(cx - STRIP_T / 2, cx + STRIP_T / 2, cy - span / 2, cy + span / 2, z - STRIP_W / 2, z + STRIP_W / 2))
        for i in range(leds):
            d = a + LED_PITCH * (i + 0.5)
            lx, ly = x0 + ux * d + nx * (STRIP_T + LED_H / 2), y0 + uy * d + ny * (STRIP_T + LED_H / 2)
            half_x = LED_SIZE / 2 if abs(ux) > 0.5 else LED_H / 2
            half_y = LED_H / 2 if abs(ux) > 0.5 else LED_SIZE / 2
            chips.append(box(lx - half_x, lx + half_x, ly - half_y, ly + half_y, z - LED_SIZE / 2, z + LED_SIZE / 2))
            count += 1
        ends.append((p0, p1, (nx, ny)))
    return Compound(children=boards), Compound(children=chips), count


CHECK_SKIP = 12.0   # route ends sit inside their connectors


def led_pads():
    runs = led_ends()
    return runs[0][0], runs[-1][1]


def wire_routes():
    """Every cable, with its terminals, waypoints and minimum bend radius in mm."""
    RED, BLK, GRN, ORG = "#d9342b", "#1b1b1b", "#2fae5e", "#f2a33a"
    jz = COVER + 7.75
    led_z = DEPTH - 7.5
    pad_a, pad_b = led_pads()
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    NX, NY = (-1, 0, 0), (0, -1, 0)
    hole_a = (STEM_X1 - LED_STEP + 5, BAND_Y + LED_STEP, led_z)
    hole_b = (STEM_X1 - LED_STEP, BAND_Y + LED_STEP - 5, led_z)
    t = PI_BOARD_Z
    xc = AUDIO_X + AUDIO_W / 2
    plug_y = AUDIO_Y - 8
    socket_y = AUDIO_Y + AUDIO_L + 2.4 + 32
    usb_x = PI_X + 87 + 32
    leg = usb_x + 17.2
    turn_y = BAND_Y + LED_STEP - 6.5
    turn_x = STEM_X1 - LED_STEP + 5.2
    top = SPK_Y1 + 6
    gap = 201.0
    sz = SCREEN_BOARD_Z - 1.8
    pwr, tch, hdm = screen_uv(129.7, 35), screen_uv(53.3, 84.4), screen_uv(108.5, 34.4)
    spk_y = SPK_Y0 + 11
    routes = [
        dict(name="12V in", colors=[ORG, BLK], od=2.4, bend=7.5, kind="18 AWG", pitch=2.5,
             start=((FOOT_W / 2, 20, 21), Y, X), start_offsets=[-3, 3], end=((CONV_GLANDS[0], CONV_Y - 5, CONV_GLAND_Z), NY, X),
             via=[(FOOT_W / 2, 48, 11), (FOOT_W / 2, 200, 11), (CONV_GLANDS[0], 225, CONV_GLAND_Z)]),
        dict(name="5V converter to junction", colors=[RED, BLK], od=2.4, bend=7.5, kind="18 AWG", pitch=2.5,
             start=((CONV_GLANDS[1], CONV_Y - 5, CONV_GLAND_Z), NY, X), end=((JUNCTION[0], 228, jz), NX, Y),
             via=[(CONV_GLANDS[1], 228, jz)], lead=2),
        dict(name="5V to Pi", colors=[RED, BLK], od=3.0, bend=8, kind="USB-C power lead", pitch=1.6, lead=2,
             start=((118, JUNCTION[2], jz), NY, X), end=((PI_X + 11.2, PI_Y - 27, t + 1.5), NY, X),
             via=[(118, 201.5, jz), (PI_X + 11.2, 201.5, jz + 2)]),
        dict(name="5V to screen", colors=[RED, BLK], od=3.0, bend=5, kind="USB-C power lead", pitch=1.6, lead=2,
             start=((124.5, JUNCTION[2], jz), NY, X), end=((pwr[0], pwr[1] - 29, sz), NY, X),
             via=[(124.5, 205, jz), (pwr[0] - 6, 205, 38), (pwr[0], 205, sz)]),
        dict(name="5V to LED start", colors=[RED, BLK], od=1.6, bend=5, kind="20 AWG", offsets=[-1.6, 1.6], end_offsets=[-3.2, 3.2], lead=2,
             start=((112, JUNCTION[2], jz), NY, Z), start_offsets=[-1.2, 1.2], end=(pad_a, NX, Z), end_lead=2.5,
             via=[(112, 206, jz), (90, 199, 26), (hole_a[0], 192, led_z), hole_a, (hole_a[0], turn_y, led_z), (pad_a[0] - 10, turn_y, led_z)]),
        dict(name="5V to LED far end", colors=[RED, BLK], od=1.6, bend=4.5, kind="20 AWG", offsets=[-1.6, 1.6], end_offsets=[-3.2, 3.2], lead=1.5,
             start=((JUNCTION[0], 223, jz), NX, Z), start_offsets=[-1.2, 1.2], end=(pad_b, Y, Z),
             end_lead=2.5, via=[(70, 223, jz), (64, 198, 34), (64, hole_b[1], led_z), hole_b, (turn_x, hole_b[1], led_z), (turn_x, pad_b[1] + 10, led_z)]),
        dict(name="LED data", colors=[GRN], od=1.6, bend=5, kind="20 AWG", lead=2,
             start=((PERF_X + 4, PERF_Y + 8, COVER + 9.6), NX, Z), end=(pad_a, NX, Z),
             via=[(124, PERF_Y + 8, 30), (112, 250, 30), (100, 207, 24), (86, 199, 30), (hole_a[0], 192, led_z), hole_a, (hole_a[0], turn_y, led_z), (pad_a[0] - 10, turn_y, led_z)], end_lead=2.5),
        dict(name="Pi GPIO to shifter", colors=[GRN, BLK], od=1.4, bend=4, kind="24 AWG", lead=2, offsets=[1.0, -1.0], start_offsets=[3.8, -3.8],
             start=((PI_X + 17.8, PI_Y + 54, t + 9), Y, X), end=((PERF_X + 15, PERF_Y + 2, COVER + 9.6), NY, X),
             via=[(PI_X + 17.8, PI_Y + 64, t + 8), (PERF_X + 15, PI_Y + 58, COVER + 18)]),
        dict(name="USB to dongle", colors=["#26262a"], od=4.0, bend=16, kind="USB cable", lead=1,
             start=((usb_x, PI_Y + 9, t + 4), X, Z), end=((xc, socket_y, COVER + 7.3), Y, Z),
             via=[(leg, PI_Y + 9, t + 4), (leg, socket_y + 22, COVER + 7.3), (xc, socket_y + 22, COVER + 7.3)]),
        dict(name="Touch USB", colors=["#26262a"], od=4.0, bend=16, kind="USB cable", lead=1,
             start=((usb_x, PI_Y + 9, t + 12), X, Z), end=((tch[0] - 9, tch[1] + 15.5, sz), Y, Z),
             via=[(leg, PI_Y + 9, t + 12), (leg, 341, 33), (tch[0] - 9, 341, sz)]),
        dict(name="Speaker pair, right", colors=[RED, BLK], od=1.2, bend=4, kind="Speaker lead", offsets=[-0.7, 0.7], start_offsets=[-3, -1], lead=2,
             start=((xc, plug_y, COVER + 7.3), NY, X), end=((209 - 1, spk_y, SPK_ZC + 9), NX, Z),
             via=[(xc - 2, top, 11), (gap + 2, top, 11), (gap + 2, spk_y, SPK_ZC + 9)], end_lead=1),
        dict(name="Speaker pair, left", colors=[RED, BLK], od=1.2, bend=4, kind="Speaker lead", offsets=[-0.7, 0.7], start_offsets=[1, 3], lead=2,
             start=((xc, plug_y, COVER + 7.3), NY, X), end=((193 + 1, spk_y, SPK_ZC - 9), X, Z),
             via=[(xc + 2, top + 3, 14), (gap - 2, top + 3, 14), (gap - 2, spk_y, SPK_ZC - 9)], end_lead=1),
        dict(name="HDMI ribbon", colors=["#6c6f76"] * 9, od=1.0, bend=5, kind="Flat ribbon", pitch=1.0, lead=4,
             start=((PI_X + 26, PI_Y - 18, t + 0.5), NY, X), end=((hdm[0], hdm[1] - 22, sz), NY, X),
             via=[(PI_X + 26, 205, t + 0.5), (hdm[0], 205, sz)], check_r=0.8),
    ]
    return [build_route(r) for r in routes]


def wire_check(routes, stand_ins, printed):
    """Sweeps each route's bundle through the model. Ends are skipped, because they sit in connectors."""
    hits = {}
    solids = {**stand_ins, **printed}
    boxes = {k: v.bounding_box() for k, v in solids.items()}
    for route in routes:
        if not route["check"]:
            continue
        points = route["center"]
        radius = route["check_r"] or max(route["r"], len(route["paths"]) * route["r"] * 0.9)
        travelled = 0.0
        total = sum(sum((points[i + 1][k] - points[i][k]) ** 2 for k in range(3)) ** 0.5 for i in range(len(points) - 1))
        i = 0
        while i < len(points) - 1:
            j = min(i + 3, len(points) - 1)
            a, b = points[i], points[j]
            seg = sum((q - p) ** 2 for p, q in zip(a, b)) ** 0.5
            travelled += seg
            if seg > 0.1 and CHECK_SKIP < travelled < total - CHECK_SKIP:
                cyl_part = Solid.make_cylinder(radius, seg, Plane(origin=a, z_dir=Vector(*[q - p for p, q in zip(a, b)])))
                bb = cyl_part.bounding_box()
                for name, shape in solids.items():
                    other = boxes[name]
                    if bb.max.X < other.min.X or bb.min.X > other.max.X or bb.max.Y < other.min.Y or bb.min.Y > other.max.Y or bb.max.Z < other.min.Z or bb.min.Z > other.max.Z:
                        continue
                    volume = overlap(cyl_part, shape)
                    if volume > 0.5:
                        key = (route["name"], name)
                        hits[key] = hits.get(key, 0) + volume
            i = j
    for (route, name), volume in hits.items():
        print(f"  {route} touches {name}: {volume:.0f} mm3")
    print(f"  {len(hits)} wire clashes")


def clip_report(routes):
    """Each clip must sit under the wire it holds, or under the part it ties down."""
    for name, x, y, _ in ZIP_CLIPS:
        if name.startswith("Converter") or name == "5V junction":
            print(f"  {name:24s} holds a part")
            continue
        nearest = min(((q[0] - x) ** 2 + (q[1] - y) ** 2) ** 0.5 for r in routes for q in r["center"])
        print(f"  {name:24s} wire {nearest:4.1f} mm away  {'ok' if nearest <= 6 else 'NO WIRE NEARBY'}")


def bend_report(routes):
    bad = 0
    for r in routes:
        actual = "straight" if r["actual"] is None else f"{r['actual']:.1f} mm"
        flag = "ok" if r["ok"] else "TOO TIGHT"
        bad += 0 if r["ok"] else 1
        print(f"  {r['name']:28s} needs {r['required']:4.1f} mm, tightest {actual:9s} length {r['length']:4d} mm  {flag}")
    print(f"  {bad} routes below their minimum radius")


SCREEN_GROUP = {"Screen", "Screen board", "Screen ports", "Screen ribbon", "Screen plugs"}
MOUNTED = {("Screen", "shell_upper"), ("Screen", "screen_clip_top_left"), ("Screen", "screen_clip_top_right"),
           ("Screen", "screen_clip_bottom_left"), ("Screen", "screen_clip_bottom_right"),
           ("Speaker left", "shell_upper"), ("Speaker right", "shell_upper"),
           ("USB audio dongle", "cover_upper"), ("USB audio dongle", "audio_strap"), ("USB audio dongle", "USB cable socket"),
           ("USB audio dongle", "Speaker plug"), ("Level shifter board", "Level shifter parts"), ("Converter", "cover_upper"), ("Level shifter board", "cover_upper"),
           ("Power jack", "shell_lower"), ("Pi case bottom", "cover_upper"), ("Pi brass spacers", "pi_bracket_left"),
           ("Pi brass spacers", "pi_bracket_low"), ("Pi brass spacers", "pi_bracket_high"), ("USB cable socket", "cover_upper")}


def front_face_check(*shells):
    """Compares the printed front face with the shape it should be, so stray holes get caught."""
    def poly_area(points):
        return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))) / 2

    slab = 0.2
    actual = sum(shell.volume - (shell - box(-10, W_TOTAL + 10, -10, H_TOTAL + 10, DEPTH - slab, DEPTH + 1)).volume for shell in shells) / slab
    expected = poly_area(inset(O, LED_STEP)) - WINDOW_W * WINDOW_H
    print(f"  face {actual:.0f} mm2, expected {expected:.0f} mm2, difference {actual - expected:.1f} mm2")


def clearance_report(stand_ins, printed):
    pi_group = {"Pi case bottom", "Pi case top", "Pi board", "Pi connectors", "Pi brass spacers", "Cable plugs"}
    names = list(stand_ins)
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if {a, b} <= pi_group or {a, b} <= SCREEN_GROUP or (a, b) in MOUNTED or (b, a) in MOUNTED:
                continue
            rows.append((stand_ins[a].distance_to(stand_ins[b]), a, b))
        for b, shape in printed.items():
            if (a, b) in MOUNTED or a.startswith("Pi ") and b == "cover_upper":
                continue
            rows.append((stand_ins[a].distance_to(shape), a, b))
    rows.sort(key=lambda r: r[0])
    for gap, a, b in rows[:14]:
        print(f"  {gap:5.1f} mm  {a} to {b}")


def overlap(a, b):
    try:
        common = a & b
        volume = common.volume if common is not None else 0
    except Exception:
        return 0.0
    return volume


def main():
    upper_box = box(-10, W_TOTAL + 10, SPLIT_SHELL, H_TOTAL + 10, -5, DEPTH + 5)
    lower_box = box(-10, W_TOTAL + 10, -10, SPLIT_SHELL, -5, DEPTH + 5)

    print("Building shell")
    shell = front_shell()
    ring = diffuser()
    cover_upper, cover_lower = back_covers()
    brackets = pi_brackets()

    parts = {
        "shell_upper": (shell & upper_box, "print", "body", "front"),
        "shell_lower": (shell & lower_box, "print", "body", "front"),
        "diffuser_upper": (ring & upper_box, "print", "diffuser", "front"),
        "diffuser_lower": (ring & lower_box, "print", "diffuser", "front"),
        "cover_upper": (cover_upper, "print", "body", "back"),
        "cover_lower": (cover_lower, "print", "body", "back"),
        "screen_clip_top_left": (screen_clip(CLAMP_XS[0], CLAMP_TOP_Y), "print", "body", "back"),
        "screen_clip_top_right": (screen_clip(CLAMP_XS[1], CLAMP_TOP_Y), "print", "body", "back"),
        "screen_clip_bottom_left": (screen_clip(CLAMP_XS[0], CLAMP_BOTTOM_Y), "print", "body", "back"),
        "screen_clip_bottom_right": (screen_clip(CLAMP_XS[1], CLAMP_BOTTOM_Y), "print", "body", "back"),
        "stem_splice": (stem_splice(), "print", "body", "back"),
        "audio_strap": (audio_strap(), "print", "body", "back"),
        "pi_bracket_left": (brackets[0], "print", "body", "back"),
        "pi_bracket_low": (brackets[1], "print", "body", "back"),
        "pi_bracket_high": (brackets[2], "print", "body", "back"),
        "test_body_corner": (shell & box(W_TOTAL - 70, W_TOTAL + 1, H_TOTAL - 70, H_TOTAL + 1, -1, DEPTH + 1), "test", "body", "front"),
        "test_diffuser_corner": (ring & box(W_TOTAL - 70, W_TOTAL + 1, H_TOTAL - 70, H_TOTAL + 1, -1, DEPTH + 1), "test", "diffuser", "front"),
    }

    for folder in ("print/black", "print/white", "print/test_pieces", "step", "viewer"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)

    print("\nPrint fit on the H2C (dual nozzle area 300 x 320 x 320, left nozzle 325 x 320 x 320)")
    manifest = []
    for name, (shape, kind, material, face) in parts.items():
        bb = shape.bounding_box()
        dims = (bb.size.X, bb.size.Y, bb.size.Z)
        ok = shape.is_valid
        footprint = sorted(dims[:2])
        print(f"  {name:22s} {dims[0]:6.1f} x {dims[1]:6.1f} x {dims[2]:5.1f}  "
              f"{'fits' if footprint[1] <= 325 and footprint[0] <= 320 else 'TOO BIG'}  valid={ok}")
        # Print files lie on the bed: the front face down for shells, the wall face down for covers.
        placed = Rot(0, 180, 0) * shape if face == "front" else shape
        low = placed.bounding_box().min
        placed = Pos(-low.X, -low.Y, -low.Z) * placed
        color = "white" if material == "diffuser" else "black"
        folder = "print/test_pieces" if kind == "test" else f"print/{color}"
        export_stl(placed, str(OUT / folder / f"{color.upper()}_{name}.stl"), tolerance=0.02, angular_tolerance=0.15)
        if kind == "print":
            export_step(shape, str(OUT / "step" / f"{name}.step"))
            export_stl(shape, str(OUT / "viewer" / f"{name}.stl"), tolerance=0.2, angular_tolerance=0.6)
            manifest.append({"name": name, "file": f"models/{name}.stl", "kind": material, "z": face})

    stand_ins = stand_in_parts()
    for name, shape in stand_ins.items():
        slug = name.lower().replace(" ", "_")
        export_stl(shape, str(OUT / "viewer" / f"part_{slug}.stl"), tolerance=0.15, angular_tolerance=0.6)
        manifest.append({"name": name, "file": f"models/part_{slug}.stl", "kind": "part", "z": "inside"})
    boards, chips, led_count = led_strip()
    routes = wire_routes()
    jumpers = led_jumpers()
    export_stl(boards, str(OUT / "viewer" / "part_led_strip.stl"), tolerance=0.2, angular_tolerance=0.6)
    export_stl(chips, str(OUT / "viewer" / "part_led_chips.stl"), tolerance=0.2, angular_tolerance=0.6)
    manifest.append({"name": "LED strip", "file": "models/part_led_strip.stl", "kind": "led", "z": "inside"})
    manifest.append({"name": "LED chips", "file": "models/part_led_chips.stl", "kind": "led", "z": "inside"})
    print(f"\nLED strip: {led_count} LEDs in {len(jumpers) + 1} sections, {len(jumpers)} corner joints")
    assembled = Compound(children=[v[0] for v in parts.values() if v[1] == "print"])
    export_step(assembled, str(OUT / "step" / "block_p_assembly.step"))
    export_stl(assembled, str(OUT / "block_p_assembly_preview.stl"), tolerance=0.1, angular_tolerance=0.4)
    clean = [{k: v for k, v in r.items() if k != "center"} for r in routes + jumpers]
    data = {"parts": manifest, "wires": clean, "size": [W_TOTAL, H_TOTAL, DEPTH],
            "picture": [SCREEN_X, SCREEN_Y, DEPTH - FRONT + 0.05, PICTURE_W, PICTURE_H]}
    (OUT / "viewer" / "manifest.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

    print("\nCollision check (0 is clean)")
    printed = {k: v[0] for k, v in parts.items() if v[1] == "print"}
    problems = 0
    names = list(stand_ins)
    for i, name in enumerate(names):
        for other in names[i + 1:]:
            volume = overlap(stand_ins[name], stand_ins[other])
            if volume > 0.5:
                print(f"  {name} hits {other}: {volume:.0f} mm3")
                problems += 1
        for part, shape in printed.items():
            volume = overlap(stand_ins[name], shape)
            if volume > 0.5:
                print(f"  {name} hits {part}: {volume:.0f} mm3")
                problems += 1
    keys = list(printed)
    for i, part in enumerate(keys):
        for other in keys[i + 1:]:
            volume = overlap(printed[part], printed[other])
            if volume > 0.5:
                print(f"  {part} hits {other}: {volume:.0f} mm3")
                problems += 1
    print(f"  {problems} collisions")

    print("\nVent check")
    vent_report()

    print("\nFront face check")
    front_face_check(printed["shell_upper"], printed["shell_lower"])

    print("\nBend radius check")
    bend_report(routes + jumpers)

    print("\nZip-tie clip check")
    clip_report(routes)

    print("\nWire route check")
    wire_check(routes, stand_ins, printed)

    print("\nSmallest gaps between parts that should not touch")
    clearance_report(stand_ins, printed)

    total = sum(shape.volume for shape, kind, _, _ in parts.values() if kind == "print") * 1.24 / 1000
    print(f"\nPrinted volume at 100% infill: about {total:.0f} g of PLA")


if __name__ == "__main__":
    main()
