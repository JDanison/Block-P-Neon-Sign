"""Option 3C (full-screen formation) with different darkening, and the band's name set like its logo:
PURDUE / All-American (script) / MARCHING BAND. Usage: python fullscreen.py <out_dir> [script_font]"""
import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops
from compose import W, H, GOLD, RUSH, HERE, fade, darken
from formation import SRC, region, duotone, marcher_mask

CREAM = (240, 232, 214)
LOGO_GOLD = (232, 190, 95)   # richer gold, closer to the logo's script
FONTS = os.path.join(HERE, "fonts")
SCRIPTS = {
    "pinyon": (os.path.join(FONTS, "PinyonScript-Regular.ttf"), 132, 2),   # file, size, extra weight
    "kunstler": ("C:/Windows/Fonts/KUNSTLER.TTF", 150, 2),
    "edwardian": ("C:/Windows/Fonts/ITCEDSCR.TTF", 150, 2),
}
SERIF = "C:/Windows/Fonts/GOUDOSB.TTF"


def draw_text(img, xy, s, f, fill, anchor="ms", spacing=0, stroke=0, glow=0):
    """Text with letter spacing, optional extra stroke weight, and a soft gold glow."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = xy
    if spacing:
        widths = [d.textlength(c, font=f) for c in s]
        x -= (sum(widths) + spacing * (len(s) - 1)) / 2
        for c, w in zip(s, widths):
            d.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1], stroke_width=stroke, stroke_fill=fill)
            x += w + spacing
    else:
        d.text((x, y), s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=fill)
    if glow:
        a = layer.getchannel("A").filter(ImageFilter.GaussianBlur(glow)).point(lambda v: min(255, int(v * 1.15)))
        img.paste(Image.new("RGB", img.size, RUSH), (0, 0), a)
    img.paste(layer, (0, 0), layer)


def title(img, cy=400, script="pinyon"):
    """The band's name, centred on (W/2, cy)."""
    path, size, weight = SCRIPTS[script]
    serif = lambda s: ImageFont.truetype(SERIF, s)
    draw_text(img, (W / 2, cy - 92), "PURDUE", serif(50), CREAM, spacing=16)
    draw_text(img, (W / 2, cy + 52), "All-American", ImageFont.truetype(path, size), LOGO_GOLD, stroke=weight, glow=6)
    draw_text(img, (W / 2, cy + 128), "MARCHING BAND", serif(40), CREAM, spacing=13)


def background(brightness=0.8):
    return ImageEnhance.Brightness(duotone(region(SRC, W, H, w_src=1920))).enhance(brightness)


# 1. Band: the 3C original, a soft horizontal band of shade behind the title.
def band():
    img = darken(background(), fade(W, H, [(0, 60), (0.25, 200), (0.75, 200), (1, 60)], horizontal=False))
    title(img); return img

# 2. Spotlight: shade only in a soft oval behind the title; the P stays bright around it.
def spotlight():
    img = background(0.85)
    oval = Image.new("L", (W, H), 0)
    ImageDraw.Draw(oval).ellipse([170, 190, 1110, 610], fill=225)
    img = darken(img, oval.filter(ImageFilter.GaussianBlur(90)))
    img = darken(img, fade(W, H, [(0, 90), (0.2, 0), (0.8, 0), (1, 90)], horizontal=False))
    title(img); return img

# 3. Frosted glass: a blurred, darkened pane with a thin gold edge behind the title.
def frosted():
    img = background(0.85)
    box = (260, 230, 1020, 590)
    pane = img.filter(ImageFilter.GaussianBlur(16))
    pane = ImageEnhance.Brightness(pane).enhance(0.38)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=26, fill=255)
    img.paste(pane, (0, 0), mask)
    edge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(box, radius=26, outline=GOLD + (150,), width=2)
    img.paste(edge, (0, 0), edge)
    title(img); return img

# 4. Marchers glow: the field goes nearly black and only the marchers stay lit, so the P itself shines.
def marchers_glow():
    bg = background(1.0)
    field = ImageEnhance.Brightness(bg).enhance(0.22)
    m = region(marcher_mask(SRC).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5)), W, H).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(2))
    img = Image.composite(bg, field, m)
    halo = m.filter(ImageFilter.GaussianBlur(10)).point(lambda v: min(255, v * 2) // 3)
    img.paste(Image.new("RGB", (W, H), (150, 110, 30)), (0, 0), halo)
    img.paste(bg, (0, 0), m)
    oval = Image.new("L", (W, H), 0)
    ImageDraw.Draw(oval).ellipse([230, 230, 1050, 580], fill=170)
    img = darken(img, oval.filter(ImageFilter.GaussianBlur(70)))
    title(img); return img

# 5. Cinematic: the whole picture dimmed evenly with darker edges, like a film title card.
def cinematic():
    img = background(0.48)
    vignette = Image.radial_gradient("L").resize((W, H))          # 0 centre, 255 corners
    img = darken(img, vignette.point(lambda v: min(255, int(v * 0.85))))
    title(img); return img

# 6. Lower third: the P stays bright at the top, with the title over a dark fade at the bottom.
def lower_third():
    img = darken(background(0.9), fade(W, H, [(0, 0), (0.38, 0), (0.62, 215), (1, 245)], horizontal=False))
    title(img, cy=560); return img


options = {"C1_band": band, "C2_spotlight": spotlight, "C3_frosted_glass": frosted,
           "C4_marchers_glow": marchers_glow, "C5_cinematic": cinematic, "C6_lower_third": lower_third}

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, make in options.items():
        make().save(os.path.join(out, f"{name}.png")); print("made", name)
    for s in ("kunstler", "edwardian"):           # same layout, other script fonts, for comparison
        img = darken(background(), fade(W, H, [(0, 60), (0.25, 200), (0.75, 200), (1, 60)], horizontal=False))
        title(img, script=s); img.save(os.path.join(out, f"font_{s}.png")); print("made font", s)
