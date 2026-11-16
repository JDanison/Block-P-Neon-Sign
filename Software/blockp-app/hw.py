"""Hardware the sign controls directly: screen brightness (DDC/CI over HDMI), speaker volume
(PipeWire), and system status. Slow commands run in the background and only the latest
request is applied, so dragging a slider never queues up a backlog."""
import asyncio, os, re, shutil, socket, subprocess, time

ENV = dict(os.environ, XDG_RUNTIME_DIR=os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
           WAYLAND_DISPLAY=os.environ.get("WAYLAND_DISPLAY", "wayland-0"))


async def run(*cmd, timeout=10) -> str:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.STDOUT, env=ENV)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return ""
    return out.decode(errors="replace")


class Latest:
    """Runs apply(value) in the background, always with the newest value, never more than one at a time."""
    def __init__(self, apply):
        self.apply, self.value, self.event, self.task = apply, None, asyncio.Event(), None

    def set(self, value):
        self.value = value
        self.event.set()
        if not self.task:
            self.task = asyncio.create_task(self._loop())

    async def _loop(self):
        while True:
            await self.event.wait()
            self.event.clear()
            try:
                await self.apply(self.value)
            except Exception as e:                       # keep going; hardware hiccups shouldn't stop the app
                print("hardware command failed:", e, flush=True)


class Display:
    """Brightness over DDC/CI (VCP 10), and true off by switching the HDMI output off.
    The screen's own DDC power-off (D6=04) only lasted about a second before the backlight came back,
    because the live HDMI signal woke it. With HDMI off the backlight stays fully dark (confirmed by eye).
    With no display, touches can't reach the app, so watch_touch() below wakes the sign instead."""
    def __init__(self):
        self.bus, self.output = None, "HDMI-A-1"
        # _was_on starts False so the first command after startup always turns the output on: a server
        # restart during night mode would otherwise leave the screen dark
        self.brightness, self.on, self._was_on = 80, True, False
        self._setter = Latest(self._apply)

    async def find_bus(self):
        out = await run("ddcutil", "detect", "--brief", timeout=20)
        m = re.search(r"/dev/i2c-(\d+)", out)
        self.bus = m.group(1) if m else None
        outputs = [l.split()[0] for l in (await run("wlr-randr")).splitlines() if l and not l[0].isspace()]
        self.output = outputs[0] if outputs else self.output
        print("screen DDC bus:", self.bus, "| output:", self.output, flush=True)

    async def _apply(self, _):
        # One worker applies the newest wish, so power and brightness commands never overlap
        if not self.on:
            await run("wlr-randr", "--output", self.output, "--off")
            self._was_on = False
            return
        if not self._was_on:
            await run("wlr-randr", "--output", self.output, "--on")
            await run("pkill", "-HUP", "-x", "kanshi")    # re-apply the 180 degree rotation (this kanshi has no kanshictl)
            self._was_on = True
            if not self.bus:
                return
            # Waking resets the panel to its own stored brightness and ignores commands for a moment,
            # so set ours, read it back, and retry until it sticks
            for _ in range(5):
                await asyncio.sleep(1.0)
                await run("ddcutil", "--bus", self.bus, "setvcp", "10", str(self.brightness))
                out = await run("ddcutil", "--bus", self.bus, "getvcp", "10")
                m = re.search(r"current value =\s*(\d+)", out)
                if m and int(m.group(1)) == self.brightness:
                    return
            print("screen brightness didn't stick after waking", flush=True)
            return
        if self.bus:
            await run("ddcutil", "--bus", self.bus, "setvcp", "10", str(self.brightness))

    def set_brightness(self, value):
        self.brightness = max(1, min(100, int(value)))
        self._setter.set(None)

    def set_power(self, on: bool):
        self.on = bool(on)
        self._setter.set(None)


async def watch_touch(on_touch):
    """Call on_touch() whenever a finger lands on the touch screen. Reads the touch device directly,
    so it works even while the HDMI output is off (night mode), when the app can't receive touches.
    Reconnects if the USB touch cable is unplugged and plugged back in."""
    import glob, struct, threading
    EVENT = struct.Struct("llHHi")                  # struct input_event on 64-bit Linux
    EV_KEY, BTN_TOUCH = 1, 330
    loop = asyncio.get_running_loop()

    async def in_thread(fn, *args):
        # A daemon thread, not the default executor: a blocking read there would hold up server shutdown
        done = loop.create_future()
        def body():
            try:
                fn(*args)
                loop.call_soon_threadsafe(done.set_result, None)
            except Exception as e:
                loop.call_soon_threadsafe(done.set_exception, e)
        threading.Thread(target=body, daemon=True).start()
        await done

    def reader(path):
        with open(path, "rb", buffering=0) as f:
            while True:
                data = f.read(EVENT.size * 32)
                for i in range(0, len(data) - EVENT.size + 1, EVENT.size):
                    _, _, etype, code, value = EVENT.unpack_from(data, i)
                    if etype == EV_KEY and code == BTN_TOUCH and value == 1:
                        loop.call_soon_threadsafe(on_touch)

    while True:
        devices = glob.glob("/dev/input/by-id/*Waveshare*event*")
        if devices:
            try:
                await in_thread(reader, devices[0])
            except OSError as e:
                print("touch screen reader stopped:", e, flush=True)
        await asyncio.sleep(5)


class Audio:
    def __init__(self):
        self._setter = Latest(self._apply)

    async def _apply(self, v):
        volume, muted = v
        await run("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume / 100:.2f}")
        await run("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if muted else "0")

    def set(self, volume, muted):
        self._setter.set((max(0, min(100, int(volume))), bool(muted)))


def ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))          # no packet is sent; this just picks the outgoing interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return ""


def system_info() -> dict:
    def cmd(*c):
        try:
            return subprocess.run(c, capture_output=True, text=True, timeout=3).stdout.strip()
        except Exception:
            return ""
    temp = cmd("vcgencmd", "measure_temp")
    throttled = cmd("vcgencmd", "get_throttled").split("=")[-1]
    disk = shutil.disk_usage("/")
    with open("/proc/uptime") as f:
        up = float(f.read().split()[0])
    ssid = cmd("iwgetid", "-r") or cmd("sh", "-c", "nmcli -t -f active,ssid dev wifi | grep '^yes' | cut -d: -f2")
    return {
        "hostname": socket.gethostname(),
        "ip": ip_address(),
        "wifi": ssid,
        "temp_c": float(temp.split("=")[1].split("'")[0]) if "=" in temp else None,
        "throttled": throttled,
        "disk_used_gb": round(disk.used / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "uptime_h": round(up / 3600, 1),
        "time": time.strftime("%Y-%m-%d %H:%M"),
        "ytdlp": cmd(os.path.join(os.path.dirname(__import__("sys").executable), "yt-dlp"), "--version"),
    }


async def power(action: str):
    if action == "reboot":
        await run("sudo", "systemctl", "reboot")
    elif action == "shutdown":
        await run("sudo", "systemctl", "poweroff")
    elif action == "restart_screen":
        await run("pkill", "-x", "chromium")          # the kiosk relaunches it within a second


# ---------- Wi-Fi (NetworkManager). A polkit rule (Pi Setup/50-blockp-network.rules) lets pi run nmcli without sudo ----------
def _fields(line):
    """Split one line of `nmcli -t` output: fields are ':'-separated, with ':' and '\\' escaped."""
    parts = re.split(r"(?<!\\):", line)
    return [p.replace("\\:", ":").replace("\\\\", "\\") for p in parts]


async def wifi_saved() -> list[dict]:
    out = await run("nmcli", "-t", "-f", "NAME,TYPE", "con", "show")
    saved = []
    for line in out.splitlines():
        f = _fields(line)
        if len(f) >= 2 and f[1] == "802-11-wireless":
            ssid = (await run("nmcli", "-t", "-g", "802-11-wireless.ssid", "con", "show", "id", f[0])).strip()
            saved.append({"name": f[0], "ssid": ssid or f[0]})
    return saved


async def wifi_scan() -> dict:
    out = await run("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list",
                    "--rescan", "yes", timeout=30)
    saved = await wifi_saved()
    saved_ssids = {s["ssid"] for s in saved}
    nets = {}
    for line in out.splitlines():
        f = _fields(line)
        if len(f) < 4 or not f[1]:
            continue                                 # hidden networks have no name to show
        ssid, signal, sec = f[1], int(f[2] or 0), f[3]
        n = nets.setdefault(ssid, {"ssid": ssid, "signal": 0, "secure": False, "connected": False,
                                   "saved": ssid in saved_ssids})
        n["signal"] = max(n["signal"], signal)       # the same network on 2.4 and 5 GHz shows twice
        n["secure"] = n["secure"] or (sec not in ("", "--"))
        n["connected"] = n["connected"] or f[0] == "*"
    networks = sorted(nets.values(), key=lambda n: (not n["connected"], -n["signal"]))
    return {"networks": networks, "saved": saved, "current": next((n["ssid"] for n in networks if n["connected"]), None)}


async def wifi_connect(ssid: str, password: str = "", hidden: bool = False) -> tuple[bool, str]:
    """Join a network. Uses the saved profile if there is one and no new password was typed.
    Returns (ok, message). Never logs the password."""
    saved = {s["ssid"]: s["name"] for s in await wifi_saved()}
    if ssid in saved and not password:
        out = await run("nmcli", "--wait", "40", "con", "up", "id", saved[ssid], timeout=50)
    else:
        cmd = ["nmcli", "--wait", "40", "dev", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        if hidden:
            cmd += ["hidden", "yes"]
        out = await run(*cmd, timeout=50)
    if "successfully activated" in out:
        return True, f"Connected to {ssid}"
    if ssid not in saved:                            # don't leave a profile with a wrong password behind
        await run("nmcli", "con", "delete", "id", ssid)
    low = out.lower()
    if "secrets were required" in low or "password" in low or "802-1x" in low:
        return False, "Wrong password. Try again."
    if "no network with ssid" in low:
        return False, f"Couldn’t find {ssid}. Move closer or check the name."
    return False, "Couldn’t connect. Try again."


async def wifi_forget(name: str):
    await run("nmcli", "con", "delete", "id", name)


async def rotate(degrees: int):
    """Flip the picture (and touch, which follows the output) between 180 (mounted) and normal (bench)."""
    await run("/usr/local/bin/blockp", "rotate", "180" if degrees == 180 else "normal")
