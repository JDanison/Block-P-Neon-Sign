# Block P CAD

Second pass of the 8" build, sized for the Bambu H2C.

## See the model

Double-click `block_p_viewer.html` to open it in a browser (needs internet for the 3D library). The online copy is linked in `PROGRESS.md`.

## Print it

Open the STL files in `print` with Bambu Studio. They're already laid flat. Print `print/test_pieces` first to check the diffuser fit and glow.

- Black: `shell_upper`, `shell_lower`, `cover_upper`, `cover_lower`, `screen_clip_top_left`, `screen_clip_top_right`, `screen_clip_bottom_left`, `screen_clip_bottom_right`, `stem_splice`, `audio_strap`, `pi_bracket_left`, `pi_bracket_low`, `pi_bracket_high`
- Translucent white: `diffuser_upper`, `diffuser_lower`

## Other files

- `step`: exact CAD files for each part, plus the full assembly
- `block_p_assembly_preview.stl`: the assembled sign, for other model viewers
- `viewer`: meshes used to build the viewer page

## Change it

`block_p.py` is the model. Every size is a named number near the top of the file, and values marked ASSUMED wait on real measurements.

To rebuild from the `Hardware/CAD` folder:

```
python -m venv .venv
.venv/Scripts/python -m pip install build123d
.venv/Scripts/python block_p.py
```

The run reports the size of each part, whether it fits the printer, and any collisions.
