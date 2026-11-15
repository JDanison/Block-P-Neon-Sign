"""Idle-screen options for the Block P sign, 1280x800 (the screen's native size).
Usage: python compose.py <out_dir>"""
import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance

W, H = 1280, 800
GOLD = (207, 185, 145)       # Purdue old gold
RUSH = (218, 170, 0)         # Purdue rush gold, for glows
HERE = os.path.dirname(os.path.abspath(__file__))
EMRICK = "C:/Purdue/Emrick/Pictures"
WEB = os.path.join(HERE, "sources")


def font(name, size, variation=None):
    f = ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    if variation:
        f.set_variation_by_name(variation)
    return f

def bahn(size, style="Bold"):
    return font("bahnschrift.ttf", size, style)

def load(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")

def cover(img, w, h, fx=0.5, fy=0.5):
    """Scale to fill w x h, then crop around the focus point (fractions of the image)."""
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = min(max(round(img.width * fx - w / 2), 0), img.width - w)
    y = min(max(round(img.height * fy - h / 2), 0), img.height - h)
    return img.crop((x, y, x + w, y + h))

def fade(w, h, stops, horizontal=True):
    """Alpha mask from (position 0..1, alpha 0..255) stops."""
    n = w if horizontal else h
    vals = []
    for i in range(n):
        t = i / (n - 1)
        for (t0, a0), (t1, a1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                vals.append(round(a0 + (a1 - a0) * (t - t0) / max(t1 - t0, 1e-9)))
                break
    line = Image.new("L", (n, 1))
    line.putdata(vals)
    if not horizontal:
        line = line.transpose(Image.ROTATE_270)   # first value ends up at the top
    return line.resize((w, h))

def darken(img, mask, color=(0, 0, 0)):
    return Image.composite(Image.new("RGB", img.size, color), img, mask)

def text(img, xy, s, f, fill=GOLD, anchor="la", spacing=0, glow=0, glow_color=RUSH):
    """Draw text with optional letter spacing and a soft glow behind it."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if spacing:
        widths = [d.textlength(c, font=f) for c in s]
        total = sum(widths) + spacing * (len(s) - 1)
        x, y = xy
        if anchor[0] == "m":
            x -= total / 2
        elif anchor[0] == "r":
            x -= total
        for c, w in zip(s, widths):
            d.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1])
            x += w + spacing
    else:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)
    if glow:
        g = layer.copy()
        r, gg, b, a = g.split()
        g = Image.merge("RGBA", (*[Image.new("L", g.size, c) for c in glow_color], a))
        g = g.filter(ImageFilter.GaussianBlur(glow))
        img.paste(g, (0, 0), g)
        img.paste(g, (0, 0), g)
    img.paste(layer, (0, 0), layer)

def logo(height):
    im = Image.open(os.path.join(WEB, "logo_gold.png")).convert("RGBA")
    im = im.crop(im.getbbox())
    return im.resize((round(im.width * height / im.height), height), Image.LANCZOS)

def rule(img, x0, x1, y, fill=GOLD, width=2):
    ImageDraw.Draw(img).line([(x0, y), (x1, y)], fill=fill, width=width)


# Option 1: Under the Lights. Full-bleed glowing-hoop photo, title low on the left.
def under_the_lights():
    img = cover(load(f"{EMRICK}/Pic2.jpg"), W, H, 0.55, 0.45)
    img = ImageEnhance.Brightness(img).enhance(0.9)
    img = darken(img, fade(W, H, [(0, 0), (0.45, 50), (0.66, 190), (1, 245)], horizontal=False))
    img = darken(img, fade(W, H, [(0, 190), (0.6, 40), (1, 0)]))
    lg = logo(96)
    img.paste(lg, (64, 520), lg)
    text(img, (64 + lg.width + 28, 520), "ALL-AMERICAN", bahn(78), spacing=4, glow=10)
    text(img, (64 + lg.width + 32, 606), "MARCHING BAND", bahn(38, "SemiBold"), fill=(240, 232, 214), spacing=11)
    rule(img, 64, 1216, 680)
    text(img, (64, 700), "PURDUE UNIVERSITY", bahn(26, "SemiLight"), fill=GOLD, spacing=8)
    return img


# Option 2: The Drum. The lit World's Largest Drum on the right, black title side on the left.
def the_drum():
    img = Image.new("RGB", (W, H), (0, 0, 0))
    drum = cover(load(f"{EMRICK}/Drum Lit Up.jpg"), 760, H, 0.62, 0.36)
    drum = ImageEnhance.Contrast(drum).enhance(1.08)
    img.paste(drum, (W - 760, 0), fade(760, H, [(0, 0), (0.32, 255), (1, 255)]))
    img = darken(img, fade(W, H, [(0, 0), (0.75, 0), (1, 200)], horizontal=False))
    x = 72
    lg = logo(120)
    img.paste(lg, (x, 150), lg)
    text(img, (x, 318), "ALL-AMERICAN", bahn(86), spacing=3, glow=12)
    text(img, (x + 4, 412), "MARCHING BAND", bahn(44, "SemiBold"), fill=(240, 232, 214), spacing=12)
    rule(img, x + 4, 560, 490)
    text(img, (x + 4, 512), "Home of the World's Largest Drum", font("georgiai.ttf", 30), fill=GOLD)
    return img


# Option 3: The Formation. The band's Block P on the field in gold duotone, matching the sign's shape.
def the_formation():
    src = load(f"{WEB}/nightblockp.jpg")
    panel = cover(src, 620, H, 0.47, 0.55)
    g = ImageOps.autocontrast(ImageOps.grayscale(panel), cutoff=1)
    panel = ImageOps.colorize(g, black=(0, 0, 0), mid=(120, 100, 60), white=(255, 236, 190))
    img = Image.new("RGB", (W, H), (0, 0, 0))
    img.paste(panel, (0, 0), fade(620, H, [(0, 255), (0.7, 255), (1, 0)]))
    x = 640
    text(img, (x, 210), "THE BLOCK P", bahn(34, "SemiBold"), fill=GOLD, spacing=14)
    text(img, (x - 3, 262), "ALL-AMERICAN", bahn(76), spacing=3, glow=12)
    text(img, (x, 350), "MARCHING BAND", bahn(40, "SemiBold"), fill=(240, 232, 214), spacing=12)
    rule(img, x, 1210, 436)
    text(img, (x, 458), "Purdue University  \u00b7  Est. 1886", font("georgiai.ttf", 30), fill=GOLD)
    return img


# Option 4: Light Show. A mosaic of the light-up uniform photos around the lit drum.
def light_show():
    img = Image.new("RGB", (W, H), (0, 0, 0))
    gap = 6
    cw = (W - 2 * gap) // 3
    th = (H - gap) // 2
    tiles = [
        ("Pic1.jpg", 0, 0, 0.5, 0.45), ("Bones.jpg", 0, 1, 0.3, 0.45),
        ("Pic3.jpg", 2, 0, 0.6, 0.5), ("Pic2.jpg", 2, 1, 0.6, 0.45),
    ]
    for name, col, row, fx, fy in tiles:
        src = load(f"{EMRICK}/{name}")
        if name == "Bones.jpg":                      # two photos side by side; keep the left one
            src = src.crop((0, 0, src.width // 2 - 4, src.height))
        t = cover(src, cw, th, fx, fy)
        img.paste(t, (col * (cw + gap), row * (th + gap)))
    centre = cover(load(f"{EMRICK}/Drum Lit Up.jpg"), cw, H, 0.62, 0.4)
    img.paste(centre, (cw + gap, 0))
    img = darken(img, fade(W, H, [(0, 0), (0.55, 0), (1, 245)], horizontal=False))
    lg = logo(64)
    img.paste(lg, ((W - lg.width) // 2, 568), lg)
    text(img, (W // 2, 648), "ALL-AMERICAN MARCHING BAND", bahn(56), anchor="ma", spacing=5, glow=12)
    return img


# Option 5: Since 1886. Historic 1921 drum photo beside today's lit drum.
def since_1886():
    img = Image.new("RGB", (W, H), (0, 0, 0))
    old = load(f"{WEB}/drum1921.png")
    old = ImageOps.colorize(ImageOps.autocontrast(ImageOps.grayscale(old)), black=(20, 16, 10), white=(236, 222, 190))
    old = cover(old, 420, 400, 0.5, 0.45)
    new = cover(load(f"{EMRICK}/Drum Lit Up.jpg"), 420, 400, 0.62, 0.36)
    for im, x, cap in ((old, 170, "1921"), (new, 690, "TODAY")):
        ImageDraw.Draw(img).rectangle([x - 6, 94, x + 426, 500], outline=GOLD, width=2)
        img.paste(im, (x, 100))
        text(img, (x + 210, 520), cap, bahn(26, "SemiBold"), fill=GOLD, anchor="ma", spacing=10)
    text(img, (W // 2, 590), "ALL-AMERICAN MARCHING BAND", bahn(62), anchor="ma", spacing=5, glow=12)
    text(img, (W // 2, 672), "Purdue University  \u00b7  Est. 1886", font("georgiai.ttf", 28), fill=GOLD, anchor="ma")
    return img


options = {
    "1_under_the_lights": under_the_lights,
    "2_the_drum": the_drum,
    "3_the_formation": the_formation,
    "4_light_show": light_show,
    "5_since_1886": since_1886,
}
if __name__ == "__main__":
  OUT = sys.argv[1]
  os.makedirs(OUT, exist_ok=True)
  for name, make in options.items():
    make().save(os.path.join(OUT, f"{name}.png"))
    print("made", name)
