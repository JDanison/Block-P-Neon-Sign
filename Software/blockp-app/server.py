"""Block P sign server: one source of truth for playback, library, lights, brightness, volume and
settings. The touch screen (Chromium kiosk, /?screen=1) and any phone or PC (/) connect over a
WebSocket and stay in sync. Run: python server.py  (port 80 under systemd, BLOCKP_PORT to change)."""
import asyncio, io, json, os, random, socket, time
from pathlib import Path

import qrcode, qrcode.image.svg
from aiohttp import web, WSMsgType

import downloader, hw, library, lights as L, settings as S

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"
BASE = Path(os.environ.get("BLOCKP_DATA", Path.home() / "blockp"))
PORT = int(os.environ.get("BLOCKP_PORT", "80"))
VERSION = "0.1"


class Sign:
    def __init__(self):
        self.settings = S.load()
        self.player = {"mode": "idle", "queue": [], "index": 0, "paused": False, "loop": False,
                       "position": 0, "duration": 0, "serial": 0}
        self.sleeping = False
        self.wifi = {"status": "idle", "ssid": None, "message": None}
        self.downloads = {}
        self.lib = {"videos": [], "albums": []}
        self.clients, self.light_watchers = set(), set()
        self.display, self.audio = hw.Display(), hw.Audio()
        self.lights = L.Lights(lambda: self.settings["lights"], self.send_frame)
        self._save_handle = None
        self._frame_n = 0

    # ---------- sending ----------
    def public_state(self):
        return {"player": self.player, "settings": self.settings, "sleeping": self.sleeping, "wifi": self.wifi,
                "downloads": list(self.downloads.values()), "version": VERSION,
                "lights_connected": self.lights.strip is not None}

    async def send(self, msg, to=None):
        data = json.dumps(msg)
        for ws in list(to if to is not None else self.clients):
            try:
                await ws.send_str(data)
            except Exception:
                self.clients.discard(ws)
                self.light_watchers.discard(ws)

    async def push_state(self):
        await self.send({"type": "state", "state": self.public_state()})

    async def push_library(self):
        await self.send({"type": "library", "library": self.lib})

    async def toast(self, text):
        await self.send({"type": "toast", "text": text})

    async def send_frame(self, frame):
        self._frame_n += 1
        if self.light_watchers and self._frame_n % 2 == 0:             # 15 fps is plenty for a preview
            await self.send({"type": "lights", "f": [c for px in frame for c in px]}, self.light_watchers)

    def save_soon(self):
        if self._save_handle:
            self._save_handle.cancel()
        self._save_handle = asyncio.get_running_loop().call_later(1.0, S.save, self.settings)

    # ---------- library ----------
    async def rescan(self):
        self.lib = await asyncio.get_running_loop().run_in_executor(None, library.scan)
        await self.push_library()

    def video_item(self, v):
        return {"kind": "video", "id": v["id"], "url": v["url"], "title": v["title"], "year": v.get("year"),
                "thumb_url": v.get("thumb_url")}

    def photo_items(self, albums):
        return [{"kind": "photo", "id": p["id"], "url": p["url"], "title": a["name"], "thumb_url": p["thumb_url"]}
                for a in albums for p in a["photos"]]

    # ---------- playback ----------
    async def play(self, items, start=0, loop=False, shuffle=False):
        items = list(items)
        if shuffle:
            random.shuffle(items)
        if not items:
            await self.toast("Nothing to play yet")
            return
        self.player.update(mode="playing", queue=items, index=start % len(items), paused=False, loop=loop,
                           position=0, duration=0, serial=self.player["serial"] + 1)
        await self.push_state()

    async def stop(self):
        self.player.update(mode="idle", queue=[], index=0, paused=False, position=0, duration=0,
                           serial=self.player["serial"] + 1)
        await self.push_state()

    async def step(self, delta):
        p = self.player
        if p["mode"] != "playing":
            return
        i = p["index"] + delta
        if i >= len(p["queue"]):
            if not p["loop"]:
                return await self.stop()
            i = 0
        p.update(index=max(0, i), paused=False, position=0, duration=0, serial=p["serial"] + 1)
        await self.push_state()

    async def startup_playback(self):
        how = self.settings["playback"]["startup"]
        vids = [self.video_item(v) for v in self.lib["videos"]]
        if how == "videos" and vids:
            await self.play(vids, loop=True)
        elif how == "shuffle_videos" and vids:
            await self.play(vids, loop=True, shuffle=True)
        elif how == "photos" and self.lib["albums"]:
            await self.play(self.photo_items(self.lib["albums"]), loop=True, shuffle=True)

    # ---------- sleep ----------
    async def set_sleep(self, on):
        if on == self.sleeping:
            return
        self.sleeping = on
        self.display.set_power(not on)               # true off: panel and backlight dark
        await self.push_state()

    async def schedule_loop(self):
        last = None
        while True:
            sch = self.settings["schedule"]
            now = time.strftime("%H:%M")
            if sch["enabled"] and now != last:
                if now == sch["off"]:
                    await self.set_sleep(True)
                elif now == sch["on"]:
                    await self.set_sleep(False)
            last = now
            await asyncio.sleep(20)

    # ---------- downloads ----------
    async def start_download(self, url, title=None, year=None):
        key = f"dl{int(time.time() * 1000)}"
        self.downloads[key] = {"key": key, "url": url, "title": title or url, "progress": 0.0,
                               "status": "starting", "error": None}
        await self.push_state()
        loop = asyncio.get_running_loop()
        last = [0.0]

        def progress(frac, status):
            def apply():
                d = self.downloads.get(key)
                if d:
                    d.update(progress=round(frac, 3), status=status)
                    if time.monotonic() - last[0] > 0.5:
                        last[0] = time.monotonic()
                        asyncio.ensure_future(self.push_state())
            loop.call_soon_threadsafe(apply)

        try:
            entry = await loop.run_in_executor(None, lambda: downloader.download(url, title, year, None, progress))
            self.downloads.pop(key, None)
            await self.rescan()
            await self.toast(f"Added “{entry['title']}”")
        except Exception as e:
            self.downloads[key].update(status="failed", error=str(e)[:200])
        await self.push_state()

    # ---------- Wi-Fi ----------
    async def join_wifi(self, ssid, password, hidden):
        self.wifi = {"status": "connecting", "ssid": ssid, "message": None}
        await self.push_state()
        try:
            ok, msg = await hw.wifi_connect(ssid, password, hidden)
        except Exception as e:
            ok, msg = False, "Couldn’t connect. Try again."
            print("wifi connect error:", type(e).__name__, flush=True)
        self.wifi = {"status": "connected" if ok else "failed", "ssid": ssid, "message": msg}
        await self.push_state()
        await self.toast(msg)
        if not ok:                                   # don't leave an old error on the Wi-Fi page forever
            await asyncio.sleep(60)
            if self.wifi["status"] == "failed":
                self.wifi = {"status": "idle", "ssid": None, "message": None}
                await self.push_state()

    # ---------- commands (from the touch screen, phone or PC) ----------
    async def command(self, c):
        t = c.get("type")
        st = self.settings
        if t == "play_video":
            vids = [self.video_item(v) for v in self.lib["videos"]]
            idx = next((i for i, v in enumerate(vids) if v["id"] == c.get("id")), None)
            if idx is not None:
                await self.play(vids, start=idx, loop=bool(c.get("continue", False)))
        elif t == "play_videos":
            await self.play([self.video_item(v) for v in self.lib["videos"]], loop=True, shuffle=c.get("shuffle", False))
        elif t == "play_album":
            albums = [a for a in self.lib["albums"] if a["name"] == c.get("name")] if c.get("name") else self.lib["albums"]
            await self.play(self.photo_items(albums), loop=True, shuffle=c.get("shuffle", False))
        elif t == "next":
            await self.step(1)
        elif t == "prev":
            await self.step(-1)
        elif t == "ended":
            if self.player["mode"] == "playing" and c.get("index") == self.player["index"]:
                await self.step(1)
        elif t in ("pause", "resume", "toggle"):
            p = self.player
            p["paused"] = (t == "pause") or (t == "toggle" and not p["paused"])
            await self.push_state()
        elif t == "seek":
            await self.send({"type": "seek", "t": float(c.get("t", 0))})
        elif t == "stop":
            await self.stop()
        elif t == "progress":
            self.player["position"], self.player["duration"] = c.get("position", 0), c.get("duration", 0)
            await self.send({"type": "progress", "position": self.player["position"],
                             "duration": self.player["duration"]})
            return
        elif t == "brightness":
            st["display"]["brightness"] = max(1, min(100, int(c["value"])))
            if not self.sleeping:
                self.display.set_brightness(st["display"]["brightness"])
        elif t == "volume":
            st["audio"]["volume"] = max(0, min(100, int(c["value"])))
            st["audio"]["muted"] = False
            self.audio.set(st["audio"]["volume"], False)
        elif t == "mute":
            st["audio"]["muted"] = bool(c.get("on", not st["audio"]["muted"]))
            self.audio.set(st["audio"]["volume"], st["audio"]["muted"])
        elif t == "lights":
            for k in ("on", "mode", "color", "brightness", "speed"):
                if k in c:
                    st["lights"][k] = c[k]
        elif t == "settings":
            self.settings = st = S.patch(st, c.get("patch", {}))
        elif t == "sleep":
            await self.set_sleep(bool(c.get("on", not self.sleeping)))
        elif t == "rotate":
            st["screen"]["rotation"] = 180 if int(c.get("degrees", 180)) == 180 else 0
            await hw.rotate(st["screen"]["rotation"])
        elif t == "power":
            self.save_now()
            await hw.power(c.get("action", ""))
            return
        elif t == "edit_video":
            library.edit_video(c["id"], c.get("title"), c.get("year"))
            await self.rescan()
        elif t == "delete_video":
            library.delete_video(c["id"])
            await self.rescan()
        elif t == "download":
            url = (c.get("url") or "").strip()
            if url.startswith("http"):
                asyncio.create_task(self.start_download(url, c.get("title") or None, c.get("year") or None))
                await self.toast("Download started")
            return
        elif t == "wifi_connect":
            ssid = (c.get("ssid") or "").strip()
            if ssid and self.wifi["status"] != "connecting":
                asyncio.create_task(self.join_wifi(ssid, c.get("password") or "", bool(c.get("hidden"))))
            return
        elif t == "wifi_forget":
            await hw.wifi_forget(c.get("name", ""))
            await self.toast("Network forgotten")
            return
        elif t == "clear_download":
            self.downloads.pop(c.get("key"), None)
        elif t == "rescan":
            await self.rescan()
            return
        else:
            return
        self.save_soon()
        await self.push_state()

    def save_now(self):
        if self._save_handle:
            self._save_handle.cancel()
        S.save(self.settings)


sign = Sign()


# ---------- HTTP ----------
async def index(request):
    return web.FileResponse(UI / "index.html", headers={"Cache-Control": "no-cache"})


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    sign.clients.add(ws)
    await ws.send_str(json.dumps({"type": "state", "state": sign.public_state()}))
    await ws.send_str(json.dumps({"type": "library", "library": sign.lib}))
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            m = json.loads(msg.data)
            if m.get("type") == "watch_lights":
                (sign.light_watchers.add if m.get("on") else sign.light_watchers.discard)(ws)
            elif m.get("type") == "cmd":
                try:
                    await sign.command(m.get("cmd", {}))
                except Exception as e:
                    safe = {k: ("***" if k == "password" else v) for k, v in m.get("cmd", {}).items()}
                    print("command failed:", safe, e, flush=True)
                    await ws.send_str(json.dumps({"type": "toast", "text": "Something went wrong"}))
    finally:
        sign.clients.discard(ws)
        sign.light_watchers.discard(ws)
    return ws


async def api_cmd(request):
    await sign.command(await request.json())
    return web.json_response({"ok": True})


async def api_state(request):
    return web.json_response(sign.public_state())


async def api_system(request):
    info = await asyncio.get_running_loop().run_in_executor(None, hw.system_info)
    info["videos"], info["albums"] = len(sign.lib["videos"]), len(sign.lib["albums"])
    return web.json_response(info)


async def api_wifi(request):
    return web.json_response(await hw.wifi_scan())


async def api_qr(request):
    url = request.query.get("u") or f"http://{socket.gethostname()}.local/"
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return web.Response(body=buf.getvalue(), content_type="image/svg+xml")


async def api_upload(request):
    reader = await request.multipart()
    album, saved = "Photos", 0
    while (part := await reader.next()) is not None:
        if part.name == "album":
            album = (await part.text()).strip() or album
        elif part.filename:
            library.save_upload(album, part.filename, await part.read())
            saved += 1
    await sign.rescan()
    await sign.toast(f"Added {saved} photo{'s' if saved != 1 else ''}")
    return web.json_response({"saved": saved})


async def lights_layout(request):
    return web.json_response({"positions": L.POSITIONS, "outline": L.OUTLINE_NORM, "screen": L.SCREEN_NORM,
                              "aspect": L.SIZE[0] / L.SIZE[1], "modes": L.MODES,
                              "colors": {k: "#%02x%02x%02x" % v for k, v in L.COLORS.items()}})


def idle_file(name):
    async def h(request):
        p = BASE / name
        if not p.exists():
            raise web.HTTPNotFound()
        return web.FileResponse(p)
    return h


async def on_startup(app):
    await sign.rescan()
    asyncio.create_task(sign.lights.run(lambda: sign.sleeping))
    asyncio.create_task(sign.schedule_loop())

    async def hardware():
        await sign.display.find_bus()
        sign.display.set_brightness(sign.settings["display"]["brightness"])
        sign.audio.set(sign.settings["audio"]["volume"], sign.settings["audio"]["muted"])
    asyncio.create_task(hardware())
    await sign.startup_playback()


async def on_shutdown(app):
    sign.save_now()


def make_app():
    app = web.Application(client_max_size=300 * 1024 * 1024)
    app.router.add_get("/", index)
    app.router.add_get("/api/ws", ws_handler)
    app.router.add_post("/api/cmd", api_cmd)
    app.router.add_get("/api/state", api_state)
    app.router.add_get("/api/system", api_system)
    app.router.add_get("/api/qr.svg", api_qr)
    app.router.add_get("/api/wifi", api_wifi)
    app.router.add_post("/api/upload", api_upload)
    app.router.add_get("/api/lights/layout", lights_layout)
    app.router.add_get("/idle.mp4", idle_file("idle.mp4"))
    app.router.add_get("/idle.png", idle_file("idle.png"))
    library.VIDEOS.mkdir(parents=True, exist_ok=True)
    library.CACHE.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/media/videos", library.VIDEOS)
    app.router.add_static("/media/cache", library.CACHE)
    app.router.add_static("/ui", UI)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), port=PORT, print=lambda *a: print(f"Block P server on port {PORT}", flush=True))
