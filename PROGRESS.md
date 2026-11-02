# Block P Sign: Progress

Last updated: November 1, 2026

## Get back to everything

- **Renders, wiring and parts:** https://claude.ai/artifact/UUrsDX5AFSufHLUw4droVF
  - This page is private to your account and pinned in your claude.ai sidebar.
  - In Claude Code, run `/artifacts` to list it. On the web, go to claude.ai/code/artifacts.
- **Saved copy of that page:** `Design Process/Renders/block-p-renders.html`. Double-click it to open it in a browser. The 3D view needs an internet connection.
- **CAD viewer:** https://claude.ai/artifact/BhFKYkZ5V4AmjUNsZYKAa3
  - Saved copy: `Hardware/CAD/block_p_viewer.html`. Use **Build guide** there for the assembly order
- **Frozen v1 viewer:** https://claude.ai/artifact/28rcgJpWbaMNy76B2Cwxvq, with files in `Hardware/CAD_v1_saved`
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
| LEDs | Your own 5V WS2812B strip, modeled as standard 10 mm 60 LED/m until confirmed. 68 LEDs in 12 sections with 11 soldered corner jumpers. Mostly solid gold or off |
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
| Pi | Online on the home network on November 1, 2026 (address in `Software/RPi IP Address.txt`, kept out of git). Nothing checked on it yet, because SSH key access isn't set up |
| LED code | `Software/LED Light Control/goldshimmer.py` runs on a test strip. It needs its brightness jump and pin notes fixed |
| Screen setup | Not started. The notes use a 3.5" script that doesn't apply to the 8" screen |
| Audio | Your speakers work with the USB audio board |
| Control software | Not started. The old Node and React work can be replaced |
| Video and photo player | Not started |
| Enclosure CAD | Current design done in build123d for the Bambu H2C. Automated checks cover collisions, the front face, wire bend radius, wire clashes and zip-tie clips. Assembly is planned as mount electronics to the back cover, connect, then fold closed, with detailed speaker, USB dongle, Pi and N300 case models. Some sizes are still estimates |
| Boot and reliability | Not started |

## Next steps

1. Order the parts in `Hardware/BOM.md`. Wait on the flat HDMI cable until CAD confirms its direction.
2. Set up SSH key access to the Pi, then change the default password. It's also written in the repo notes.
3. Print the test pieces in `Hardware/CAD/print/test_pieces` to check the diffuser and screw hole size.
4. Measure the speakers and USB dongle you already have. When the other parts arrive, measure them against the list on the CAD viewer page, then update the model.
5. Send the list of YouTube show links by year, plus any photos.
6. Test everything together on the bench, including connecting the cover and folding it closed before printing the full sign.
7. Build the software, then the CAD, then assemble.

## Open questions

- Is the existing test LED strip worth reusing, or should the new strip be used?
- Does the Lithophane White PLA diffuse the strip well enough? Test this with a small print.
- Do you want the LED branch fuse?
