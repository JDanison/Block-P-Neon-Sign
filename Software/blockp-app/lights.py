"""Gold LED outline: 68 WS2812B LEDs around the P. Renders frames at 30 fps for the real strip
(when it's connected) and streams them to the screens for a live preview.

The outline and LED count come from Hardware/CAD/block_p.py (outline O, in mm, y up)."""
import asyncio, colorsys, math, random, time

N = 204                 # 5 mm FCOB strip, 160 LEDs/m, 12 sections (Hardware/CAD/block_p.py prints the count)
FPS = 30
# Power limit. The FCOB strip is rated 12 W per meter at full white: 12 / 5 V / 160 LEDs = 15 mA per
# LED, 5 mA per color. That puts all 204 LEDs at full white near 3.1 A. Frames are scaled so the
# estimate never passes this budget, under the LED branch's 5 A fuse. Check MA_PER_CHANNEL once with a
# meter at full white: if the real draw is higher, raise it so the limit stays honest.
LED_BUDGET_A = 4.0
MA_PER_CHANNEL = 5.0
OUTLINE = [(0, 0), (120.33, 0), (120.33, 63), (91.67, 63), (91.67, 163.8), (322.67, 163.8),
           (322.67, 382.8), (0, 382.8), (0, 319.8), (28.67, 319.8), (28.67, 63), (0, 63)]
SIZE = (322.67, 382.8)

COLORS = {                                    # names shown in the app -> LED RGB (tuned for WS2812B, not screens)
    "gold": (255, 85, 0),                     # John's tested strip gold, 195:65:0 from the old goldshimmer.py
    "old_gold": (255, 175, 70),
    "warm_white": (255, 190, 120),
    "white": (255, 255, 255),
}
MODES = ["solid", "breathe", "shimmer", "chase", "wave", "sparkle", "march", "rainbow"]


def _led_positions():
    """Spread N LEDs evenly around the outline, inset slightly. Returns (x, y) as 0..1 with y down."""
    pts = OUTLINE + [OUTLINE[0]]
    segs = [(pts[i], pts[i + 1]) for i in range(len(OUTLINE))]
    lengths = [math.dist(a, b) for a, b in segs]
    total = sum(lengths)
    out = []
    for k in range(N):
        d = (k + 0.5) * total / N
        for (a, b), L in zip(segs, lengths):
            if d <= L:
                t = d / L
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                out.append((round(x / SIZE[0], 4), round(1 - y / SIZE[1], 4)))
                break
            d -= L
    return out

POSITIONS = _led_positions()
OUTLINE_NORM = [(round(x / SIZE[0], 4), round(1 - y / SIZE[1], 4)) for x, y in OUTLINE]
# Screen window from block_p.py: centre (175.67, 273.3) mm, 188 x 113 mm, y up
SCREEN_NORM = (round((175.67 - 94) / SIZE[0], 4), round(1 - (273.3 + 56.5) / SIZE[1], 4),
               round(188 / SIZE[0], 4), round(113 / SIZE[1], 4))          # x, y, w, h with y down


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Lights:
    def __init__(self, get_state, on_frame):
        self.get_state = get_state            # returns the lights settings dict
        self.on_frame = on_frame              # called with the frame (list of [r, g, b]) for previews
        self.strip = self._open_strip()
        self.seed = [random.random() for _ in range(N)]
        self.sparks = [0.0] * N
        self.level = 0.0                      # fades the whole strip on/off smoothly
        self.amps = 0.0                       # estimated strip current for the last frame, after limiting

    def _open_strip(self):
        try:
            from rpi_ws281x import PixelStrip      # installed once the strip is wired up
            s = PixelStrip(N, 18, 800000, 10, False, 255, 0)
            s.begin()
            print("LED strip connected", flush=True)
            return s
        except Exception as e:
            print("LED strip not connected, preview only:", type(e).__name__, flush=True)
            return None

    def color(self, st):
        c = st.get("color", "gold")
        return COLORS.get(c) or (hex_rgb(c) if isinstance(c, str) and c.startswith("#") else COLORS["gold"])

    def render(self, t, st):
        mode, speed = st.get("mode", "solid"), float(st.get("speed", 1.0))
        r, g, b = self.color(st)
        px = [0.0] * N                         # brightness 0..1 per LED, tinted by colour below
        rgb_override = None
        if mode == "solid":
            px = [1.0] * N
        elif mode == "breathe":
            v = 0.2 + 0.8 * (0.5 - 0.5 * math.cos(2 * math.pi * t * speed / 4))
            px = [v] * N
        elif mode == "shimmer":
            px = [0.55 + 0.45 * (0.5 + 0.5 * math.sin(2 * math.pi * (t * speed * (0.3 + s * 0.5) + s * 7)))
                  for s in self.seed]
        elif mode == "chase":
            head = (t * speed * N / 3) % N
            for i in range(N):
                d = (head - i) % N
                px[i] = max(0.06, math.exp(-d / 6))
        elif mode == "wave":
            px = [0.15 + 0.85 * (0.5 + 0.5 * math.sin(2 * math.pi * (2 * i / N - t * speed / 2))) for i in range(N)]
        elif mode == "sparkle":
            for i in range(N):
                if random.random() < 0.02 * speed:
                    self.sparks[i] = 1.0
                self.sparks[i] *= 0.88
            px = [0.18 + 0.82 * s for s in self.sparks]
        elif mode == "march":                  # blocks step one LED per beat at 120 bpm, like 8-to-5
            step = int(t * 2 * speed)
            rgb_override = []
            for i in range(N):
                on = ((i + step) // 4) % 2 == 0
                rgb_override.append((r, g, b) if on else (60, 60, 60))
            px = [1.0] * N
        elif mode == "rainbow":
            rgb_override = [tuple(int(c * 255) for c in colorsys.hsv_to_rgb((i / N + t * speed / 8) % 1, 1, 1))
                            for i in range(N)]
            px = [1.0] * N
        target = 1.0 if st.get("on", True) else 0.0
        self.level += (target - self.level) * 0.15
        k = self.level * max(0, min(100, st.get("brightness", 70))) / 100
        base = rgb_override or [(r, g, b)] * N
        frame = [[c * p * k for c in col] for col, p in zip(base, px)]
        amps = sum(sum(px_) for px_ in frame) / 255 * MA_PER_CHANNEL / 1000
        scale = min(1.0, LED_BUDGET_A / amps) if amps > 0 else 1.0
        self.amps = amps * scale
        return [[int(c * scale) for c in col] for col in frame]

    async def run(self, sleeping):
        t0 = time.monotonic()
        while True:
            st = dict(self.get_state())
            if sleeping():
                st["on"] = False
            frame = self.render(time.monotonic() - t0, st)
            if self.strip:
                for i, (r, g, b) in enumerate(frame):
                    self.strip.setPixelColorRGB(i, r, g, b)
                self.strip.show()
            await self.on_frame(frame)
            await asyncio.sleep(1 / FPS)
