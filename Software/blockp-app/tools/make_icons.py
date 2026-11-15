"""App icons for "Add to Home Screen": the Block P drawn to the formation's people counts (the same
shape as the sign), gold on near-black. Usage: python tools/make_icons.py  (writes ui/icons/)"""
import os
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ui", "icons")
GOLD, GOLD_HI = (218, 170, 0), (240, 200, 90)


def block_p(size, scale):
    """The P in grid units: 21 wide x 24 tall (stem 3, base 7x3, top band 3, screen opening 13x8)."""
    u = size * scale / 24
    w, h = 21 * u, 24 * u
    ox, oy = (size - w) / 2, (size - h) / 2
    rects = [(0, 0, 21, 3), (2, 0, 5, 24), (18, 0, 21, 14), (2, 11, 21, 14), (0, 21, 7, 24)]
    return [(ox + x0 * u, oy + y0 * u, ox + x1 * u, oy + y1 * u) for x0, y0, x1, y1 in rects]


def icon(size, scale):
    img = Image.new("RGB", (size, size), (14, 13, 12))
    # soft gold glow behind the P, like the LED outline
    glow = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(glow)
    for r in block_p(size, scale):
        d.rectangle(r, fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(size / 28)).point(lambda v: v * 0.55)
    img.paste(Image.new("RGB", img.size, GOLD), (0, 0), glow)
    # the P, with a subtle top-to-bottom gold gradient
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    for r in block_p(size, scale):
        d.rectangle(r, fill=255)
    grad = Image.linear_gradient("L").resize((size, size))
    fill = Image.composite(Image.new("RGB", img.size, GOLD), Image.new("RGB", img.size, GOLD_HI), grad)
    img.paste(fill, (0, 0), mask)
    return img


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    icon(512, 0.62).save(os.path.join(OUT, "icon-512.png"))
    icon(192, 0.62).save(os.path.join(OUT, "icon-192.png"))
    icon(180, 0.62).save(os.path.join(OUT, "apple-touch-icon.png"))   # iOS rounds the corners itself
    icon(512, 0.48).save(os.path.join(OUT, "icon-maskable-512.png"))  # extra margin for Android's shape masks
    print("icons written to", os.path.normpath(OUT))
