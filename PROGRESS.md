# Block P Sign: Progress

Last updated: November 1, 2026

## Get back to everything

- **Renders, wiring and parts:** https://claude.ai/artifact/UUrsDX5AFSufHLUw4droVF
  - This page is private to your account and pinned in your claude.ai sidebar.
  - In Claude Code, run `/artifacts` to list it. On the web, go to claude.ai/code/artifacts.
- **Saved copy of that page:** `Design Process/Renders/block-p-renders.html`. Double-click it to open it in a browser. The 3D view needs an internet connection.
- **Parts list:** `Hardware/BOM.md`
- **This file:** `PROGRESS.md`, in the project's top folder

## Project goal

A wall-mounted, 3D-printed keepsake of four years in the Purdue All-American Marching Band, shaped like the band's Block P. It plays show videos and photos, has a thin gold LED outline, and is controlled from a computer or phone on the home network. One power cord runs down the wall.

## Decisions

| Item | Decision |
|---|---|
| Shape | Locked. Taken from the drill chart, then adjusted by hand |
| Screen location | Fills the opening of the P |
| Screen | Waveshare 8DP-CAPLCD, 8", 1280 x 800 |
| Sign size | About 14.5 x 11.9 in, with about 50 mm depth (estimate) |
| Print | Black body, translucent white LED diffuser |
| Speakers | Your QCCAN 8 ohm 5W speakers, mounted in the band under the screen and firing down |
| LEDs | 5V WS2812B strip, about 1.6 m, mostly solid gold or off |
| Power | 12V 5A adapter into a 10A 5V converter, with separate 5V branches for the Pi, screen and LEDs |
| Fuses | No 12V fuse. A 5A fuse on the LED branch is optional and recommended |
| Software | One Python service on the Pi that runs the LEDs, plays media with `mpv` and serves a React control page |
| Access | Home network only, at `blockp.local` |

## Locked shape

Grid units, with x to the right and y up from the foot's lower left corner. The 8" build uses 11.9 mm per unit.

- **Outline:** (0,0) (9,0) (9,4) (6.5,4) (6.5,13) (25.5,13) (25.5,31) (0,31) (0,27) (2.5,27) (2.5,4) (0,4)
- **Screen opening:** x 6 to 22, y 16 to 28

## Status

| Area | Status |
|---|---|
| Design and renders | Done |
| Parts list | Done, nothing ordered that I know of |
| Pi | Online on the home network on November 1, 2026 (address in `Software/RPi IP Address.txt`, kept out of git). Nothing checked on it yet, because SSH key access isn't set up |
| LED code | `Software/LED Light Control/goldshimmer.py` runs on a test strip. It needs its brightness jump and pin notes fixed |
| Screen setup | Not started. The notes use a 3.5" script that doesn't apply to the 8" screen |
| Audio | Your speakers work with the USB audio board |
| Control software | Not started. The old Node and React work can be replaced |
| Video and photo player | Not started |
| Enclosure CAD | Not started. Needs the real parts to measure |
| Boot and reliability | Not started |

## Next steps

1. Order the parts in `Hardware/BOM.md`. Wait on the flat HDMI cable until CAD confirms its direction.
2. Set up SSH key access to the Pi, then change the default password. It's also written in the repo notes.
3. Measure the screen thickness, speaker depth and converter size.
4. Tell Claude which Bambu printer you have.
5. Send the list of YouTube show links by year, plus any photos.
6. Test everything together on the bench.
7. Build the software, then the CAD, then assemble.

## Open questions

- Is the existing test LED strip worth reusing, or should the new strip be used?
- Does the Lithophane White PLA diffuse the strip well enough? Test this with a small print.
- Do you want the LED branch fuse?
