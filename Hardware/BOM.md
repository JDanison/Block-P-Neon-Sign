# Block P Sign: Bill of Materials

For the locked Block P shape with the 8" screen: about 15.4 x 12.6 x 2.2 in, black print, a 5 mm FCOB WS2812B strip at 160 LEDs/m (204 LEDs, about 1.3 m in 12 sections).

Only the screen's details come from the maker. Other details are seller listings, so check each listing before buying.

## Buy

| Part | Spec | Notes |
|---|---|---|
| [Waveshare 8DP-CAPLCD 8" screen](https://www.amazon.com/dp/B0BPMCTQQ8) | 1280 x 800 HDMI | Includes HDMI, USB, micro-HDMI adapter and spacers |
| [Meiyue 12V 5A adapter](https://www.amazon.com/dp/B0BPSQ84TT) | 60W, 5.5 x 2.1 mm plug | About 5 ft cord. Check it is center positive |
| Female DC jack with screw terminal | 5.5 x 2.1 mm, 2-way screw terminal | Often included with 12V adapters; buy a pack if yours wasn't. It sits in a pocket on the lower cover under a printed strap, and the cord plugs in through the bottom of the foot. Measure its body for the CAD (modeled as 30 x 14 x 11.5 mm) |
| [uxcell 12V to 5V converter, 10A 50W](https://www.amazon.com/dp/B01ENT1PPM) | 12V/24V in, fixed 5V 10A out, potted, 64 x 57 x 22 mm | Replaces the KNACRO, which went out of stock. Fits the CAD pocket as is. Backups that also fit, all on Amazon: [Aweking B06WWBDW31](https://www.amazon.com/dp/B06WWBDW31) (57 x 64 x 22 mm, turned sideways), [YAXIGE B0G2S9VRZQ](https://www.amazon.com/dp/B0G2S9VRZQ) (58 x 40 x 22 mm, add a foam pad) and [DROK B00CEP3A0Q](https://www.amazon.com/dp/B00CEP3A0Q) (65 x 58 x 22 mm). The pocket fits any potted 5V 10A module up to 66 x 60 x 22 mm. Assume no reverse-polarity protection, so confirm the adapter is center positive before connecting |
| [Vovucai USB-C power leads, 5 pack](https://www.amazon.com/dp/B0F31YX6XX) | 22 AWG, 5V 3A | Uses 2. Cut to about 30 cm |
| [SN74AHCT125N, 5 pack](https://www.amazon.com/dp/B08FHD994N) | 3.3V to 5V level shifter | Skip if you have one |
| [chenyang flat HDMI to micro-HDMI cable](https://www.amazon.com/dp/B01367WEI4) | 0.2 m, straight plugs at both ends | The CAD uses straight plugs at both ends. If the listing offers angled versions, pick the straight one |
| USB-A to side-angle USB-C cable | About 1 ft, straight USB-A, side-angle USB-C, must carry data | For touch. A side-angle plug turns the cable flat along the screen board. The CAD route is 254 mm between the plugs, so 6 in is too short |
| [Geekworm N300 heatsink case](https://www.amazon.com/dp/B07X5Y81C6) | 16 mm thick, for Pi 4 | Cools the Pi with no fan |
| [Glvaner M3 x 10 mm self-tapping screws, 100 pack](https://www.amazon.com/dp/B09NPL4P9W) | 304 stainless steel, pan washer head | Uses 46 |
| [PATIKIL perfboard, 24 pack](https://www.amazon.com/dp/B0CBPRBRTT) | 1.2 x 1.2 in | Holds the level shifter |
| [eSUN Lithophane White PLA+, 1 kg](https://www.amazon.com/dp/B0D7PZS1VV) | LED diffuser | Translucent white. Test with your strip first |
| [FCOB WS2812B strip, 6.56 ft](https://www.amazon.com/dp/B0FL7GKGVM) | 5V, 160 LEDs/m, 5 mm wide | The sign's LED outline: 204 LEDs, about 1.3 m. Check where its cut marks are; the CAD assumes every LED (6.25 mm) |

## Optional

| Part | Spec | Notes |
|---|---|---|
| [YUNPICAR fuse holders, 2 pack](https://www.amazon.com/dp/B09539L14T) | 18 AWG, with 5A mini blade fuses | LED branch, recommended |
| [Fancasee DC extension cord](https://www.amazon.com/dp/B09SZ88S1Y) | 6 ft, 18 AWG, 5.5 x 2.1 mm | If the 5 ft cord falls short. Check that it is rated for 3A or more |

## Small hardware

Needed for the current CAD model, if you don't already have them.

- 10 small zip ties, 3.6 mm wide or narrower
- 2 wall screws with heads under 9 mm and shafts under 5 mm
- 4 stick-on rubber bumpers, about 8 mm tall
- CA glue and thin foam tape
- Stranded 26 AWG wire for 33 corner jumpers (28 AWG for the one tight corner), and 22 AWG red and black for the level shifter's 5V

## Already owned

Raspberry Pi 4B, microSD card, Waveshare USB to Audio dongle and its short USB extension cable, QCCAN 8 ohm 5W speakers (about 100 x 45 x 21 mm, holes 92 x 36 mm, mounted under the screen firing down), wire, heat shrink, resistor, capacitor, multimeter, black filament, soldering gear and a Bambu printer.
