"""Hardware the sign controls directly: screen brightness (DDC/CI over HDMI), speaker volume
(PipeWire), and system status. Slow commands run in the background and only the latest
request is applied, so dragging a slider never queues up a backlog."""
import asyncio, os, re, shutil, socket, subprocess, time

ENV = dict(os.environ, XDG_RUNTIME_DIR=os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


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
    """Brightness (VCP 10) and true power off (VCP D6). D6=04 turns the panel and backlight fully
    off (confirmed by eye on the Waveshare 8"), while HDMI, the app and touch keep running."""
    def __init__(self):
        self.bus = None
        # _was_on starts False so the first command after startup always sends "power on": a server
        # restart during night mode would otherwise leave the panel dark
        self.brightness, self.on, self._was_on = 80, True, False
        self._setter = Latest(self._apply)

    async def find_bus(self):
        out = await run("ddcutil", "detect", "--brief", timeout=20)
        m = re.search(r"/dev/i2c-(\d+)", out)
        self.bus = m.group(1) if m else None
        print("screen DDC bus:", self.bus, flush=True)

    async def _apply(self, _):
        # One worker applies the newest wish, so brightness and power commands never collide on the I2C bus
        if not self.bus:
            return
        if not self.on:
            await run("ddcutil", "--bus", self.bus, "setvcp", "D6", "04")
            self._was_on = False
            return
        if not self._was_on:
            await run("ddcutil", "--bus", self.bus, "setvcp", "D6", "01")
            self._was_on = True
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
        await run("ddcutil", "--bus", self.bus, "setvcp", "10", str(self.brightness))

    def set_brightness(self, value):
        self.brightness = max(1, min(100, int(value)))
        self._setter.set(None)

    def set_power(self, on: bool):
        self.on = bool(on)
        self._setter.set(None)


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
