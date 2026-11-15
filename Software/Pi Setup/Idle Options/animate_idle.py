"""Animated version of the chosen idle screen (option 5, bright cinematic). Makes a seamless loop:
the camera drifts slowly over the formation, the gold glow breathes, and once per loop a light
sweeps across "All-American". Usage: python animate_idle.py <out.mp4> [seconds] [fps]"""
import sys, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops
import imageio_ffmpeg
from compose import W, H, RUSH
from formation import SRC, region, duotone
from fullscreen import SCRIPTS, SERIF, CREAM, LOGO_GOLD
from blends import corners

OUT = sys.argv[1]
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 24
FPS = int(sys.argv[3]) if len(sys.argv) > 3 else 30
FRAMES = round(SECONDS * FPS)

# Background, 10% bigger than the screen so the camera has room to drift. The centre window
# matches the still image exactly.
BW, BH = round(W * 1.1), round(H * 1.1)
BIG = ImageEnhance.Brightness(duotone(region(SRC, BW, BH, w_src=1920 * 1.1))).enhance(0.62)
SHADE = corners(0.65)                       # same dark corners as the still, fixed to the screen
BLACK = Image.new("RGB", (W, H), (0, 0, 0))


def spaced(d, cx, y, s, f, fill, spacing):
    widths = [d.textlength(c, font=f) for c in s]
    x = cx - (sum(widths) + spacing * (len(s) - 1)) / 2
    for c, w in zip(s, widths):
        d.text((x, y), c, font=f, fill=fill, anchor="ls")
        x += w + spacing

# Title layers, laid out exactly like fullscreen.title() with cy = 400
cy = 400
serif_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(serif_layer)
spaced(d, W / 2, cy - 92, "PURDUE", ImageFont.truetype(SERIF, 50), CREAM, 16)
spaced(d, W / 2, cy + 128, "MARCHING BAND", ImageFont.truetype(SERIF, 40), CREAM, 13)

path, size, weight = SCRIPTS["pinyon"]
script_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(script_layer).text((W / 2, cy + 52), "All-American", font=ImageFont.truetype(path, size),
                                  fill=LOGO_GOLD, anchor="ms", stroke_width=weight, stroke_fill=LOGO_GOLD)
script_alpha = script_layer.getchannel("A")
glow_base = script_alpha.filter(ImageFilter.GaussianBlur(6))
x0, _, x1, _ = script_alpha.getbbox()
RUSH_IMG = Image.new("RGB", (W, H), RUSH)
SHINE_IMG = Image.new("RGB", (W, H), (255, 244, 214))


def frame(t):
    """t runs 0..1 around the loop; every motion is periodic in t, so the end meets the start."""
    a = 2 * math.pi * t
    z = 1.0 + 0.0125 * (1 - math.cos(a))                    # push in to 2.5% and back
    cx = BW / 2 + 40 * math.sin(a)                           # slow ellipse
    cyb = BH / 2 + 16 * math.cos(a)
    s = 1 / z
    img = BIG.transform((W, H), Image.AFFINE, (s, 0, cx - s * W / 2, 0, s, cyb - s * H / 2), Image.BICUBIC)
    img = Image.composite(BLACK, img, SHADE)

    pulse = 0.82 + 0.18 * (0.5 - 0.5 * math.cos(2 * a))        # glow breathes twice per loop
    img.paste(RUSH_IMG, (0, 0), glow_base.point(lambda v: min(255, int(v * 1.15 * pulse))))
    img.paste(script_layer, (0, 0), script_layer)

    sweep = (t - 0.10) / 0.12                                # light sweep, 0..1 during 10-22% of the loop
    if 0 <= sweep <= 1:
        sx = x0 - 120 + (x1 - x0 + 240) * (0.5 - 0.5 * math.cos(math.pi * sweep))
        band = Image.new("L", (W, 1))
        band.putdata([int(150 * math.exp(-((x - sx) / 55) ** 2)) for x in range(W)])
        band = band.resize((W, H))
        img.paste(SHINE_IMG, (0, 0), ImageChops.multiply(band, script_alpha))

    img.paste(serif_layer, (0, 0), serif_layer)
    return img


if __name__ == "__main__":
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-level", "4.1",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(FRAMES):
        f = frame(i / FRAMES)
        if i == 0:
            f.save(OUT.rsplit(".", 1)[0] + "_poster.png")
        enc.stdin.write(f.tobytes())
        if i % 120 == 0:
            print(f"frame {i}/{FRAMES}", flush=True)
    enc.stdin.close()
    sys.exit(enc.wait())
