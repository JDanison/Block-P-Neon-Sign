# Block P sign app

The software that runs the sign: playback, the touch-screen menu, lights, brightness, volume, settings and downloads. The same page runs on the sign's screen and on phones and PCs, and all of them stay in sync.

- **On the sign:** Chromium shows `http://127.0.0.1/?screen=1` fullscreen. It plays media, and a frosted-glass menu drops down when you touch the screen.
- **On a phone or PC:** open `http://blockp.local`, or scan the code under **Phone** in the menu. It's the same controls, used as a remote.

## Files

| File | What it does |
|---|---|
| `server.py` | The sign's server (aiohttp, port 80). It holds all state and pushes every change to every screen over a WebSocket |
| `hw.py` | Screen brightness over HDMI (DDC/CI, `ddcutil`), volume (`wpctl`), system info, restart and shutdown |
| `lights.py` | The 68-LED outline: 8 effects rendered at 30 fps. It drives the strip once it's connected; until then it's a live preview |
| `library.py` | Videos, photo albums and resized photo copies in `~/blockp/library` |
| `downloader.py` | Saves a video from a link (yt-dlp) as H.264 720p at 30 fps, so it plays without the internet |
| `settings.py` | Saved settings in `~/blockp/settings.json`, written atomically so a power cut can't corrupt them |
| `ui/` | The interface: `index.html`, `app.css`, `app.js`, bundled icons and the Inter font. Nothing loads from the internet |
| `kiosk.sh` | Starts Chromium fullscreen on the sign (run by the kiosk session) |
| `blockp.service` | Starts the server at boot (`/etc/systemd/system/`) |

## Measured on the Pi 4

- **Video format:** 720p at 30 fps plays with no dropped frames under the frosted menu. 1080p60 dropped over half its frames, so the downloader converts everything to 720p30, once, after download. The screen is 1280×800, so nothing visible is lost.
- **Menu blur:** to keep video smooth under the menu, the blur is 28 px. The layer behind the menu has no tint. Hidden glass elements switch their blur off. Tiles sit on their own compositing layers, and the small LED preview redraws at about 4 fps. Each of these was measured. Together, video drops under 1% of frames with the menu open, and none on the Settings page.

## Install or update on the Pi

```
~/blockp/venv/bin/pip install -r requirements.txt     # once
sudo cp blockp.service /etc/systemd/system/ && sudo systemctl enable --now blockp
sudo systemctl restart blockp                          # after changing Python files
blockp restart                                         # after changing ui/ files (reloads the screen)
```

The kiosk session itself, including screen rotation, auto-login and the `blockp` command, is set up by the files in `../Pi Setup`.

## LED strip (when it's connected)

- **Wiring:** data comes from GPIO18 (PWM) through the SN74AHCT125 level shifter and a 330 Ω resistor. Strip power comes from the 5V converter, not the Pi, at both ends, with a 1000 µF capacitor.
- **Driver:** install with `~/blockp/venv/bin/pip install rpi_ws281x`. `lights.py` finds it on the next start (`blockp restart-server`). The library needs root access to the PWM hardware, so the service may need to run as root, or use the SPI pin instead. Check this when the strip is wired.
- **Gold:** the "Gold" color is the one you tuned on the real strip in the old `goldshimmer.py`, 195:65:0, scaled to full. That file's shimmer became the **Shimmer** effect.

## Library, updates and backup

- **Library → Edit:** reorder each season with the arrows. **Play all** switches each video in or out of Play all and startup playback; tapping a video still plays it either way. Tapping an album opens it to play, rename (on a phone or PC), delete the album, or delete single photos.
- **Settings → Downloader → Update:** installs the newest yt-dlp and restarts the server (under a second). Use it when YouTube downloads start failing; automatic updates are off on purpose.
- **Settings → Backup** (on a phone or PC): **Download backup** saves your settings and the video list with source links. **Restore** puts them back and re-downloads missing videos, one at a time. **Download photos** zips every album.

## Wi-Fi

To change networks, go to **Settings**, then **Wi-Fi**, then **Change network**. It lists nearby networks, and you type the password on the on-screen keyboard. Saved networks rejoin with no typing, hidden networks are under **Other network**, and **Forget** removes old ones. The sign uses NetworkManager through `nmcli`, which needs `../Pi Setup/50-blockp-network.rules` installed.

Without Wi-Fi, everything on the sign keeps working, because the page loads only from the Pi. Phones can't reach the sign, new videos can't download, and the clock can't sync. The Pi 4 has no battery-backed clock.

## Add videos

- **From a phone:** open the menu, then **Phone**, then **Add**, and paste a YouTube link.
- **From the Pi's terminal:** `blockp add <link> --title "2023 Halftime" --year 2023`

Converting a 60 fps video takes about 2.5 times its length, once, after it downloads.
