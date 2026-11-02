# Block P CAD

The current 8" build, sized for the Bambu H2C.

## See the model

Double-click `block_p_viewer.html` to open it in a browser (needs internet for the 3D library). The online copy is linked in `PROGRESS.md`. Use **Build guide** above the model for the assembly order.

## Print it

Drag the STL files into Bambu Studio. They're already laid flat, and every filename starts with its filament color. The full list is in `print/PRINT_LIST.md`.

- `print/black`: 13 files, for black filament
- `print/white`: 2 files, for translucent white filament
- `print/test_pieces`: print these 3 first to check the diffuser fit, glow and screw hole size

## Files

| File | Purpose |
|---|---|
| `block_p.py` | The model and its checks. Every size is a named number near the top, and values marked ASSUMED wait on real measurements |
| `wiring.py` | Builds wire routes with real bend arcs |
| `assembly_check.py` | Simulates the build order |
| `build_viewer.py` and `viewer_src` | Build the viewer page |
| `print` | STL files for printing, sorted by filament color |
| `step` | Exact CAD files for each part, plus the full assembly |
| `block_p_assembly_preview.stl` | The assembled sign, for other model viewers |

`Hardware/CAD_v1_saved` is a frozen copy from before the Build guide was added.

## Rebuild

From the `Hardware/CAD` folder:

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python block_p.py
.venv/Scripts/python build_viewer.py
```

`block_p.py` reports each part's fit on the printer, collisions, the front face check, wire bend radii, zip-tie clips, wire clashes and the smallest gaps between parts.
