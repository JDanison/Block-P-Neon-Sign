"""Variations on the 'Block P formation' idle screen. Usage: python formation.py <out_dir>"""
import sys, os
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance, ImageChops
from compose import W, H, GOLD, RUSH, WEB, bahn, font, load, fade, darken, text, logo, rule

CREAM = (240, 232, 214)
GREY = (150, 140, 120)
PAD_X, PAD_Y = 200, 300
_photo = load(f"{WEB}/nightblockp.jpg")         # 1920 x 2102
SRC = Image.new("RGB", (_photo.width + 2 * PAD_X, _photo.height + 2 * PAD_Y))
_edges = ImageChops.multiply(                    # soften the photo's own edges into the black margin
    fade(_photo.width, _photo.height, [(0, 0), (0.06, 255), (0.94, 255), (1, 0)]),
    fade(_photo.width, _photo.height, [(0, 0), (0.08, 255), (0.86, 255), (0.93, 0), (1, 0)], horizontal=False))
SRC.paste(_photo, (PAD_X, PAD_Y), _edges)       # black margin so the whole P fits any panel
P_BOX = (100 + PAD_X, 560 + PAD_Y, 1800 + PAD_X, 1790 + PAD_Y)   # the formation inside SRC
P_CX, P_CY = (P_BOX[0] + P_BOX[2]) // 2, (P_BOX[1] + P_BOX[3]) // 2
PANEL_W = 640


def panel_mask(side="left"):
    """Fade the panel's inner edge, plus its top and bottom, into the black background."""
    across = [(0, 255), (0.93, 255), (1, 0)] if side == "left" else [(0, 0), (0.07, 255), (1, 255)]
    h = fade(PANEL_W, H, across)
    v = fade(PANEL_W, H, [(0, 60), (0.12, 255), (0.88, 255), (1, 60)], horizontal=False)
    return ImageChops.multiply(h, v)


def region(src, w_out, h_out, cx=None, cy=None, w_src=2000):
    """Crop around (cx, cy) with w_src source pixels across, at the output's aspect, then resize."""
    cx = P_CX if cx is None else cx
    cy = P_CY if cy is None else cy
    h_src = w_src * h_out / w_out
    if h_src > src.height:
        h_src = src.height
        w_src = h_src * w_out / h_out
    x0 = min(max(cx - w_src / 2, 0), src.width - w_src)
    y0 = min(max(cy - h_src / 2, 0), src.height - h_src)
    return src.crop((round(x0), round(y0), round(x0 + w_src), round(y0 + h_src))).resize((w_out, h_out), Image.LANCZOS)

def duotone(img):
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    return ImageOps.colorize(g, black=(0, 0, 0), mid=(120, 100, 60), white=(255, 236, 190))

def marcher_mask(src):
    """White uniforms only, inside the formation: bright, low-colour pixels, thin yard lines removed."""
    r, g, b = src.split()
    white = ImageChops.darker(ImageChops.darker(r, g), b)            # min(R,G,B): high only for white
    spread = ImageChops.subtract(ImageChops.lighter(ImageChops.lighter(r, g), b), white)
    mask = ImageChops.multiply(white.point(lambda v: 255 if v > 150 else 0),
                               spread.point(lambda v: 255 if v < 70 else 0))
    mask = mask.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))   # opening removes lines
    keep = Image.new("L", src.size, 0)
    ImageDraw.Draw(keep).rectangle(P_BOX, fill=255)
    return ImageChops.multiply(mask, keep)

def formation_cells():
    """The sign's own shape in marchers (block_p.py): 21 wide x 24 tall, row 0 at the top."""
    cells = set()
    def block(x0, y0, x1, y1):
        cells.update((x, y) for x in range(x0, x1) for y in range(y0, y1))
    block(0, 0, 21, 3)      # top band; its left 2 are the top-left block
    block(2, 3, 5, 24)      # stem, 3 wide
    block(18, 3, 21, 11)    # right side of the screen opening (opening is 13 x 8)
    block(2, 11, 21, 14)    # band under the screen
    block(0, 21, 7, 24)     # base, 7 x 3
    return cells

def neon(w_out, h_out, cell=25):
    """Each dot is one marcher, glowing gold like the sign's LED outline. The drum sits in the opening."""
    dots = Image.new("L", (w_out, h_out), 0)
    d = ImageDraw.Draw(dots)
    ox, oy = (w_out - 21 * cell) / 2, (h_out - 24 * cell) / 2
    for gx, gy in formation_cells():
        cx, cy = ox + (gx + 0.5) * cell, oy + (gy + 0.5) * cell
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=255)
    dx, dy = ox + 11.5 * cell, oy + 7 * cell          # centre of the opening
    d.ellipse([dx - 24, dy - 24, dx + 24, dy + 24], outline=255, width=4)
    d.ellipse([dx - 4, dy - 4, dx + 4, dy + 4], fill=200)
    out = Image.new("RGB", (w_out, h_out), (0, 0, 0))
    for radius, gain, colour in ((14, 2.5, (140, 95, 0)), (5, 2.0, RUSH)):
        m = dots.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: min(255, int(v * gain)))
        out.paste(Image.new("RGB", out.size, colour), (0, 0), m)
    out.paste(Image.new("RGB", out.size, (255, 236, 190)), (0, 0), dots)
    return out

def title_block(img, x, y, kicker="THE BLOCK P", sub="Purdue University  ·  Est. 1886", width=570, anchor="l"):
    """The title stack from option 3. anchor 'l' = left aligned at x, 'm' = centred on x."""
    a = "la" if anchor == "l" else "ma"
    text(img, (x, y), kicker, bahn(34, "SemiBold"), fill=GOLD, spacing=14, anchor=a)
    text(img, (x - (3 if anchor == "l" else 0), y + 52), "ALL-AMERICAN", bahn(76), spacing=3, glow=12, anchor=a)
    text(img, (x, y + 140), "MARCHING BAND", bahn(40, "SemiBold"), fill=CREAM, spacing=12, anchor=a)
    x0 = x if anchor == "l" else x - width / 2
    rule(img, x0, x0 + width, y + 226)
    if sub:
        text(img, (x, y + 248), sub, font("georgiai.ttf", 30), fill=GOLD, anchor=a)


def panel(make):
    return make(region(SRC, PANEL_W, H))

# A. The original, reframed so the whole P is in the panel.
def whole_p():
    img = Image.new("RGB", (W, H))
    img.paste(panel(duotone), (0, 0), panel_mask("left"))
    title_block(img, 668, 212)
    return img

# B. Mirrored: title on the left, formation on the right.
def mirrored():
    img = Image.new("RGB", (W, H))
    img.paste(panel(duotone), (W - PANEL_W, 0), panel_mask("right"))
    title_block(img, 64, 212)
    return img

# C. Full screen: the whole formation fills the screen, with a dark band behind the title.
def full_bleed():
    img = duotone(region(SRC, W, H, w_src=1920))
    img = ImageEnhance.Brightness(img).enhance(0.8)
    band = fade(W, H, [(0, 60), (0.22, 205), (0.62, 205), (0.8, 60), (1, 60)], horizontal=False)
    img = darken(img, band)
    title_block(img, W // 2, 196, anchor="m", width=600)
    return img

# D. Natural colour: the real green field under the lights, slightly toned toward gold.
def natural():
    img = Image.new("RGB", (W, H))
    photo = ImageEnhance.Color(panel(lambda p: p)).enhance(0.75)
    photo = Image.blend(photo, duotone(photo), 0.25)
    img.paste(photo, (0, 0), panel_mask("left"))
    title_block(img, 668, 212)
    return img

# E. Neon: only the marchers, as a grid of glowing gold LEDs, like the sign's own outline.
def neon_formation():
    img = Image.new("RGB", (W, H))
    img.paste(neon(PANEL_W, H), (0, 0), panel_mask("left"))
    title_block(img, 668, 212)
    return img

# F. Personal: the original layout with the years you marched and the gold P mark.
def my_years():
    img = Image.new("RGB", (W, H))
    img.paste(panel(duotone), (0, 0), panel_mask("left"))
    title_block(img, 668, 150, sub=None)
    text(img, (668, 410), "2022 – 2025", bahn(64, "Light"), fill=CREAM, spacing=6)
    text(img, (668, 492), "FOUR SEASONS  ·  PURDUE UNIVERSITY", bahn(22, "SemiBold"), fill=GOLD, spacing=6)
    lg = logo(70)
    img.paste(lg, (W - lg.width - 60, H - 70 - 56), lg)
    return img


options = {
    "3A_whole_p": whole_p, "3B_mirrored": mirrored, "3C_full_screen": full_bleed,
    "3D_natural_color": natural, "3E_neon": neon_formation, "3F_my_years": my_years,
}
if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, make in options.items():
        make().save(os.path.join(out, f"{name}.png"))
        print("made", name)
