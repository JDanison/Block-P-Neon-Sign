# Pi kiosk setup

These files make the Pi boot straight into the sign app (`../blockp-app`), fullscreen, with the screen rotated 180 degrees to match how it's mounted in the sign. The app is covered in its own README.

## Where each file goes on the Pi

| File | Goes to | What it does |
|---|---|---|
| `blockp-session` | `/usr/local/bin/` | Starts labwc with only the Block P config, so the desktop panel and file manager never load |
| `blockp-kiosk.desktop` | `/usr/share/wayland-sessions/` | Adds the Block P kiosk as a login session |
| `autostart` | `~/.config/blockp-labwc/` | Starts kanshi and the app's `kiosk.sh`. Copy `environment` from `~/.config/labwc/` into the same folder |
| `rc.xml` | `~/.config/blockp-labwc/` | Maps touch to the screen with `mouseEmulation="no"`, so Chromium gets real finger input. With emulation on, touches arrive as mouse clicks: no finger scrolling, and a little lag |
| `kanshi-config` | `~/.config/kanshi/config` | Rotates the screen 180 degrees. Touch is mapped to the screen in `rc.xml`, so it rotates too (tested: taps land where you touch) |
| `idle.mp4`, `idle.png` | `~/blockp/` | The idle screen: option 5, "bright cinematic". The animated loop comes from `Idle Options/animate_idle.py`, the still from `bright_cinematic()` in `Idle Options/blends.py` |
| `blockp` | `/usr/local/bin/` | The commands below |
| `50-blockp-network.rules` | `/etc/polkit-1/rules.d/` | Lets the sign's account change Wi-Fi without sudo, for the Wi-Fi page in Settings. Without sudo, Wi-Fi passwords never land in sudo's command log |
| `Idle Options/` | (not copied to the Pi) | The scripts that made the idle screen. `blends.py` makes `idle.png` and `animate_idle.py` makes `idle.mp4`. The other scripts made the earlier options and still supply shared pieces |

To use the kiosk session, set `autologin-session=blockp-kiosk` in `/etc/lightdm/lightdm.conf`. To switch off screen blanking, run `sudo raspi-config nonint do_blanking 1`.

## Power-cut protection and reliability (set up November 15, 2026)

- **Logs:** kept in RAM (`/etc/systemd/journald.conf.d/blockp.conf`)
- **Watchdog:** the hardware watchdog reboots the Pi if it ever freezes (`/etc/systemd/system.conf.d/blockp-watchdog.conf`, 15 s)
- **Updates:** the update timers are off (`apt-daily`, `apt-daily-upgrade`, `man-db`), so the sign never updates itself mid-use
- **Saved files:** settings, downloads and uploads are written to a temporary file and then renamed, so a power cut leaves the old or the new copy, never a broken one
- **Browser:** Chromium's profile lives in RAM, so the browser writes nothing to the SD card
- **Already in Pi OS:** `noatime` mounts, a filesystem check and repair at every boot, and swap that's compressed in RAM

A fully read-only system would need a separate data partition on the SD card. Setting that up is easiest when the card is reflashed.

## Commands on the Pi

```
blockp status               screen rotation, kiosk, server, browser, number of videos
blockp rotate 180|normal    flip the picture and touch (use normal on the bench)
blockp kiosk on|off         sign app at boot, or the normal Pi desktop
blockp restart              reload the screen
blockp restart-server       restart the sign server
blockp add <link> [--title T] [--year Y]   download a video to the sign
blockp logs                 recent server messages
```

The Pi's name is `blockp`, so it's at `blockp.local` on the home network.
