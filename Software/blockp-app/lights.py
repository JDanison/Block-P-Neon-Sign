"""Gold LED outline: 204 WS2812B LEDs around the P. Renders frames on a fixed clock for the real
strip (when it's connected) and streams them to the screens for a live preview.

The outline and LED count come from Hardware/CAD/block_p.py (outline O, in mm, y up).

Every effect moves by a phase that advances by (seconds x speed) each frame, so changing the speed
only changes how fast the pattern moves from now on; it never jumps. The speed itself eases to the
slider's value, and brightness, on/off, effect and colour changes all fade instead of snapping."""
import asyncio, colorsys, math, random, time

N = 204                 # 5 mm FCOB strip, 160 LEDs/m, 12 sections (Hardware/CAD/block_p.py prints the count)
FPS = 60                # strip refresh. 204 LEDs take 6.1 ms to send, so 60 fps leaves plenty of room
# Power limit. The FCOB strip is rated 12 W per meter at full white: 12 / 5 V / 160 LEDs = 15 mA per
# LED, 5 mA per color. That puts all 204 LEDs at full white near 3.1 A. Frames are scaled so the
# estimate never passes this budget, under the LED branch's 5 A fuse. Check MA_PER_CHANNEL once with a
# meter at full white: if the real draw is higher, raise it so the limit stays honest.
LED_BUDGET_A = 4.0
MA_PER_CHANNEL = 5.0
# LEDs are linear: half the PWM looks much brighter than half. The strip gets each LED's level raised
# to this power, so fades and the brightness slider look on the strip the way they look in the preview.
# Full level is unchanged, so the tuned gold stays exactly as tuned. 1.0 turns the correction off.
GAMMA = 2.2
EASE = {"speed": 0.35, "level": 0.25, "brightness": 0.15}   # seconds to cover ~63% of a change
CROSSFADE = 0.5                                              # seconds to blend to a new effect or colour

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
TAU = 2 * math.pi


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


def ease(current, target, dt, tau):
    """Move current toward target, covering ~63% of the gap every tau seconds, whatever the frame rate."""
    return target + (current - target) * math.exp(-dt / tau)


class Lights:
    def __init__(self, get_state, on_frame):
        self.get_state = get_state            # returns the lights settings dict
        self.on_frame = on_frame              # called with the frame (list of [r, g, b]) for previews
        self.strip = self._open_strip()
        self.seed = [random.random() for _ in range(N)]
        self.rate = [0.3 + s * 0.5 for s in self.seed]     # shimmer: each LED's own pace
        self.sparks = [0.0] * N
        self.phase = 0.0                      # effect time: advances by seconds x speed
        self.speed = None                     # eased speed, starts at the saved value
        self.level = 0.0                      # fades the whole strip on/off smoothly
        self.bright = None                    # eased brightness 0..1
        self.look = None                      # (mode, colour) being shown, to spot changes
        self.fade_from, self.fade_t = None, 1.0   # last look's colours, and crossfade progress 0..1
        self.colors = [(0.0, 0.0, 0.0)] * N   # last frame's full-level colours, before brightness
        self.residual = [0.0] * (N * 3)       # dithering: the fraction each channel couldn't show yet
        self.amps = 0.0                       # estimated strip current for the last frame, after limiting
        self.strip_k = 0.0                    # level the strip gets: brightness after the curve and power limit

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

    def pattern(self, mode, rgb, dt):
        """Each LED's colour at full brightness for the current phase: a list of (r, g, b)."""
        p, (r, g, b) = self.phase, rgb
        if mode == "breathe":
            v = 0.2 + 0.8 * (0.5 - 0.5 * math.cos(TAU * p / 4))
            return [(r * v, g * v, b * v)] * N
        if mode == "shimmer":
            out = []
            for s, k in zip(self.seed, self.rate):
                v = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(TAU * (p * k + s * 7)))
                out.append((r * v, g * v, b * v))
            return out
        if mode == "chase":
            head = (p * N / 3) % N
            out = []
            for i in range(N):
                v = max(0.06, math.exp(-((head - i) % N) / 6))
                ahead = (i - head) % N             # the head fades in over 1.5 LEDs, so it glides
                if ahead < 1.5:                    # between LEDs instead of hopping from one to the next
                    v = max(v, 0.06 + 0.94 * (1 - ahead / 1.5))
                out.append((r * v, g * v, b * v))
            return out
        if mode == "wave":
            out = []
            for i in range(N):
                v = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(TAU * (2 * i / N - p / 2)))
                out.append((r * v, g * v, b * v))
            return out
        if mode == "sparkle":
            chance, keep = 0.6 * self.speed * dt, math.exp(-3.84 * self.speed * dt)   # 2% a frame, x0.88, at 30 fps
            sp = self.sparks
            for i in range(N):
                if random.random() < chance:
                    sp[i] = 1.0
                sp[i] *= keep
            return [(r * (0.18 + 0.82 * s), g * (0.18 + 0.82 * s), b * (0.18 + 0.82 * s)) for s in sp]
        if mode == "march":                    # blocks step one LED per beat at 120 bpm, like 8-to-5
            step = int(p * 2)
            return [(r, g, b) if ((i + step) // 4) % 2 == 0 else (60, 60, 60) for i in range(N)]
        if mode == "rainbow":
            return [tuple(c * 255 for c in colorsys.hsv_to_rgb((i / N + p / 8) % 1, 1, 1)) for i in range(N)]
        return [(r, g, b)] * N                 # solid

    def render(self, dt, st):
        """Advance by dt seconds and return the preview frame: [[r, g, b], ...] as screens should show it."""
        mode = st.get("mode", "solid")
        rgb = self.color(st)
        target_speed = max(0.0, float(st.get("speed", 1.0)))
        target_bright = max(0, min(100, st.get("brightness", 70))) / 100
        if self.speed is None:
            self.speed, self.bright = target_speed, target_bright
        self.speed = ease(self.speed, target_speed, dt, EASE["speed"])
        self.bright = ease(self.bright, target_bright, dt, EASE["brightness"])
        self.level = ease(self.level, 1.0 if st.get("on", True) else 0.0, dt, EASE["level"])
        self.phase += dt * self.speed

        look = (mode, rgb)
        if look != self.look:                  # new effect or colour: blend from what was showing
            if self.look is not None:
                self.fade_from, self.fade_t = self.colors, 0.0
            self.look = look
        cols = self.pattern(mode, rgb, dt)
        if self.fade_t < 1.0:
            self.fade_t = min(1.0, self.fade_t + dt / CROSSFADE)
            w = self.fade_t * self.fade_t * (3 - 2 * self.fade_t)
            cols = [(a[0] + (c[0] - a[0]) * w, a[1] + (c[1] - a[1]) * w, a[2] + (c[2] - a[2]) * w)
                    for a, c in zip(self.fade_from, cols)]
        self.colors = cols

        k = self.level * self.bright
        if k < 0.002:                          # off, or faded out: skip the work
            self.amps, self.strip_k = 0.0, 0.0
            return [[0, 0, 0]] * N
        # Current estimate uses what the strip actually gets (after the curve), then scales both outputs.
        sk = k ** GAMMA
        amps = sum(c[0] + c[1] + c[2] for c in cols) * sk / 255 * MA_PER_CHANNEL / 1000
        scale = min(1.0, LED_BUDGET_A / amps) if amps > 0 else 1.0
        self.amps = amps * scale
        self.strip_k = sk * scale
        pk = k * scale ** (1 / GAMMA)          # the preview dims by the same amount, as eyes would see it
        return [[int(c[0] * pk + 0.5), int(c[1] * pk + 0.5), int(c[2] * pk + 0.5)] for c in cols]

    def show(self):
        """Send the last frame to the strip, with the curve and temporal dithering: each channel
        carries the fraction it couldn't show into the next frame, so slow fades stay smooth even
        where 8-bit steps are coarse."""
        k, res, strip = self.strip_k, self.residual, self.strip
        j = 0
        for i, c in enumerate(self.colors):
            out = []
            for v in c:
                v = v * k + res[j]
                q = min(255, max(0, int(v + 0.5)))
                res[j] = v - q if 0 < v < 255 else 0.0
                out.append(q)
                j += 1
            strip.setPixelColorRGB(i, out[0], out[1], out[2])
        strip.show()

    async def run(self, sleeping):
        """Frames on a fixed clock: each one is due at start + n / FPS, so slow frames never make
        the animation drift, and a late frame catches up instead of stretching time."""
        loop = asyncio.get_running_loop()
        step = 1 / (FPS if self.strip else 30)   # preview only: 30 fps is all the screens use
        last = due = loop.time()
        while True:
            now = loop.time()
            st = dict(self.get_state())
            if sleeping():
                st["on"] = False
            frame = self.render(min(now - last, 0.25), st)   # cap dt so a stall can't leap the pattern
            if self.strip:
                self.show()
            last = now
            await self.on_frame(frame)
            due += step
            wait = due - loop.time()
            if wait < -step:                   # far behind (busy CPU): skip ahead instead of rushing
                due = loop.time()
                wait = 0
            await asyncio.sleep(max(0.0, wait))
