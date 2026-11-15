"""More takes on C2 (spotlight) and C5 (cinematic). Saves clean images to <out>/clean and
copies with a small number in the bottom-right corner to <out>/labeled, for comparing on the sign.
Usage: python blends.py <out_dir>"""
import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops
from compose import W, H, fade, darken
from formation import SRC, region, duotone, marcher_mask
from fullscreen import title, background, spotlight, cinematic


def oval(box, strength, blur):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse(box, fill=strength)
    return m.filter(ImageFilter.GaussianBlur(blur))

def corners(strength):
    """Radial vignette: 0 in the centre, rising toward the corners."""
    return Image.radial_gradient("L").resize((W, H)).point(lambda v: min(255, int(v * strength)))

OVAL = [170, 190, 1110, 610]


# 3. Blend: C2's oval behind the name plus C5's dark corners, at C2's brightness.
def blend():
    img = darken(background(0.8), oval(OVAL, 215, 90))
    img = darken(img, corners(0.7))
    title(img); return img

# 4. Wide spotlight: a bigger, gentler oval, so more of the formation stays fully lit.
def wide_spotlight():
    img = darken(background(0.9), oval([90, 150, 1190, 650], 185, 120))
    img = darken(img, fade(W, H, [(0, 70), (0.18, 0), (0.82, 0), (1, 70)], horizontal=False))
    title(img); return img

# 5. Brighter cinematic: C5 with less dimming and lighter corners.
def bright_cinematic():
    img = darken(background(0.62), corners(0.65))
    title(img); return img

# 6. Spotlight with the marchers kept bright: the field dims a little, the P stays lit, oval behind the name.
def spotlight_marchers():
    bg = background(1.0)
    field = ImageEnhance.Brightness(bg).enhance(0.3)
    m = region(marcher_mask(SRC).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5)), W, H)
    img = Image.composite(bg, field, m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(2)))
    img = darken(img, oval(OVAL, 200, 90))
    img = darken(img, corners(0.55))
    title(img); return img

# 7. Deep cinematic: richer contrast (deeper blacks, brighter highlights) with dark corners.
def deep_cinematic():
    img = background(1.0)
    img = img.point(lambda v: int(255 * (v / 255) ** 1.6))       # gamma curve: shadows drop, highlights stay
    img = ImageEnhance.Brightness(img).enhance(0.85)
    img = darken(img, corners(0.8))
    img = darken(img, oval(OVAL, 120, 100))
    title(img); return img

# 8. Widescreen: C2 with thin black film bars at the top and bottom.
def widescreen():
    img = spotlight()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 54], fill=(0, 0, 0)); d.rectangle([0, H - 54, W, H], fill=(0, 0, 0))
    return img

# 9. Tilt-shift: the band across the middle stays sharp, top and bottom go soft, plus C5's corners.
def tilt_shift():
    sharp = background(0.75)
    soft = sharp.filter(ImageFilter.GaussianBlur(7))
    keep = fade(W, H, [(0, 0), (0.3, 255), (0.7, 255), (1, 0)], horizontal=False)
    img = Image.composite(sharp, soft, keep)
    img = darken(img, oval(OVAL, 170, 90))
    img = darken(img, corners(0.7))
    title(img); return img

# 10. Gold glow: C2, with a faint warm gold light rising from behind the name.
def gold_glow():
    img = darken(background(0.8), oval(OVAL, 225, 90))
    glow = oval([340, 300, 940, 520], 70, 80)
    img.paste(Image.new("RGB", (W, H), (200, 150, 40)), (0, 0), glow)
    img = darken(img, corners(0.5))
    title(img); return img


options = [("01_C2_spotlight", spotlight), ("02_C5_cinematic", cinematic), ("03_blend", blend),
           ("04_wide_spotlight", wide_spotlight), ("05_bright_cinematic", bright_cinematic),
           ("06_spotlight_marchers", spotlight_marchers), ("07_deep_cinematic", deep_cinematic),
           ("08_widescreen", widescreen), ("09_tilt_shift", tilt_shift), ("10_gold_glow", gold_glow)]

if __name__ == "__main__":
    out = sys.argv[1]
    for sub in ("clean", "labeled"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    label_font = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", 40)
    for name, make in options:
        img = make()
        img.save(os.path.join(out, "clean", f"{name}.png"))
        num = name.split("_")[0].lstrip("0")
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([W - 98, H - 76, W - 22, H - 22], radius=10, fill=(0, 0, 0), outline=(207, 185, 145), width=2)
        d.text((W - 60, H - 49), num, font=label_font, fill=(255, 255, 255), anchor="mm")
        img.save(os.path.join(out, "labeled", f"{name}.png"))
        print("made", name)
