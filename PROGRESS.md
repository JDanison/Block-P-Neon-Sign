# Block P Sign: Progress

Last updated: November 19, 2026

## Get back to everything

- **Everything in one link:** https://claude.ai/artifact/7JiZs627D4oxsy8ad2iG6d
  - Three tabs: **Render**, **CAD & BoM** (model, build guide, print list, files, parts list) and **Wiring & install** (wiring diagram, level shifter, bring-up order, cable routes, assembly notes). Add `#cad` or `#install` to the link to open a tab directly.
  - Rebuild it after either page below changes: `python "Design Process/build_combined.py"` writes `Design Process/block-p-sign.html`, then republish that file.
  - The two pages below are its sources and still work on their own.
- **Renders, wiring and parts:** https://claude.ai/artifact/UUrsDX5AFSufHLUw4droVF
  - This page is private to your account and pinned in your claude.ai sidebar.
  - In Claude Code, run `/artifacts` to list it. On the web, go to claude.ai/code/artifacts.
- **Saved copy of that page:** `Design Process/Renders/block-p-renders.html`. Double-click it to open it in a browser. The 3D view needs an internet connection.
- **CAD viewer:** https://claude.ai/artifact/BhFKYkZ5V4AmjUNsZYKAa3
  - Saved copy: `Hardware/CAD/block_p_viewer.html`. Use **Build guide** there for the assembly order
- **CAD files:** `Hardware/CAD`, with print files in `Hardware/CAD/print`
- **Parts list:** `Hardware/BOM.md`
- **This file:** `PROGRESS.md`, in the project's top folder

## Project goal

A wall-mounted, 3D-printed keepsake of four years in the Purdue All-American Marching Band, shaped like the band's Block P. It plays show videos and photos, has a thin gold LED outline, and is controlled from a computer or phone on the home network. One power cord runs down the wall.

## Decisions

| Item | Decision |
|---|---|
| Shape | Locked. Taken from the drill chart, then adjusted by hand |
| Screen location | Fills the opening of the P |
| Screen | Waveshare 8DP-CAPLCD, 8", 1280 x 800, 194 x 119 x 5 mm (11 mm with its board). Mounted rotated 180 degrees with 4 corner clips, and rotated back in software |
| Sign size | About 15.1 x 12.7 x 2.2 in (383 x 323 x 55 mm). The renders page still shows an earlier size |
| Print | Black body, translucent white LED diffuser |
| Speakers | Your QCCAN 8 ohm 5W speakers (about 100 x 45 x 21 mm, holes 92 x 36 mm), mounted under the screen and firing down |
| Printer | Bambu H2C, with the sign printed in two main sections |
| LEDs | FCOB WS2812B, 5 mm wide, 160 LEDs/m: 204 LEDs in 12 sections with 11 soldered corner jumpers (26 AWG, 28 AWG at the tight corner). Mostly solid gold or off |
| Power | 12V 5A adapter into a 10A 5V converter, with separate 5V branches for the Pi, screen and LEDs |
| Fuses | No 12V fuse. A 5A fuse on the LED branch is optional and recommended |
| Software | One Python service on the Pi that runs the LEDs, plays media with `mpv` and serves a React control page |
| Access | Home network only, at `blockp.local` |

## Locked shape

Proportions come from the band's formation, counted in people. One person is 14.33 mm of visible black, a size set by the H2C's 325 mm bed. `Hardware/CAD/block_p.py` checks these on every rebuild.

- **Stem:** 3 people wide
- **Base:** 7 people wide by 3 people tall, so it sticks out 2 people on each side of the stem
- **Top-left block:** 3 people tall, and 2 people past the stem, lined up with the left edge of the base
- **Screen border:** 3 people on the top, bottom, left and right

## Status

| Area | Status |
|---|---|
| Design and renders | Done |
| Parts list | Done, nothing ordered that I know of |
| Pi | Set up November 15, 2026. It's named `blockp` (`blockp.local`), uses SSH keys only, and passed a power test. The old school project is backed up and removed. The address is in `Software/RPi IP Address.txt`, which is kept out of git |
| LED code | Done in `Software/blockp-app/lights.py`, with 8 effects, your tested gold color, and 204 LEDs for the 5 mm FCOB strip. A current limiter caps the strip at 4 A, using the strip's 12 W/m rating. It shows a live preview until the strip is connected, then needs the `rpi_ws281x` driver installed. Updated November 20, 2026: the off button works, speed changes glide instead of jumping, effects and colors crossfade, and the strip will run at 60 fps with gamma correction. Not yet copied to the Pi |
| Screen setup | Done November 15, 2026. The 8" screen and touch work, rotated 180 degrees for mounting. Brightness control over HDMI works. The screen needs its own USB-C power: powered from the Pi alone, it overloads the Pi's USB ports |
| Kiosk | Done November 15, 2026. The Pi boots in about 20 seconds straight into the sign app, with no desktop. On the Pi, run `blockp` to see the commands |
| Touch app | First version done November 15, 2026 (`Software/blockp-app`). Touching the screen drops down a frosted-glass control center with now playing, brightness, volume, lights, video and photo library, night mode, a phone QR code, and settings. Phones and PCs get the same controls at `blockp.local` |
| Audio | Your speakers work with the USB audio board |
| Control software | Done. The touch screen, plus phone, tablet and desktop layouts with Add to Home Screen. There's also library editing, a downloader update button, and backup and restore |
| Video and photo player | Done. It plays videos and photo slideshows with slow pan and zoom, and shows an animated idle screen. The downloader saves YouTube links as 720p30, the format measured to play smoothly under the frosted menu |
| Enclosure CAD | Current design done in build123d for the Bambu H2C. Automated checks cover collisions, the front face, wire bend radius, wire clashes and zip-tie clips. Assembly is planned as mount electronics to the back cover, connect, then fold closed, with detailed speaker, USB dongle, Pi and N300 case models. Some sizes are still estimates. Updated November 19, 2026: a 9 mm channel for the 5 mm strip, a DC jack pocket and strap on the lower cover, the level shifter's 5V lead, and a side-angle touch cable. Every check passes |
| Boot and reliability | Done November 15, 2026. Logs are kept in RAM, the hardware watchdog is on, automatic updates are off, saved files survive power cuts, and the Pi is renamed to `blockp` |

## Next steps

1. Send the YouTube show links by year, plus any photos. They're tracked in `Software/show-links.md`.
2. Print the test pieces in `Hardware/CAD/print/test_pieces` to check the diffuser and screw hole size.
3. Measure the screen board, speakers and USB dongle, then update the CAD model.
4. Order the remaining parts in `Hardware/BOM.md`.
5. Wire the LED strip and install its driver.
6. Test everything together on the bench, including a heat test inside the closed enclosure, before printing the full sign.

## Open questions

- Does the Lithophane White PLA diffuse the strip well enough? Test this with a small print.
- Do you want the LED branch fuse?
