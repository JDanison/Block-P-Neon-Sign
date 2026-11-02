"""
    Filename: build_viewer.py
    Description:
        Packs the meshes from block_p.py and the page in viewer_src into one file,
        block_p_viewer.html. Run block_p.py first.

    Run:
        .venv/Scripts/python -m pip install pillow
        .venv/Scripts/python build_viewer.py
"""

import base64
import io
import json
import pathlib
import sys

from PIL import Image

CAD = pathlib.Path(__file__).parent
PHOTO = CAD.parent.parent / "Software" / "Images" / "Background" / "OregonBlockP.JPG"


def photo_uri():
    image = Image.open(PHOTO).convert("RGB")
    width, height = image.size
    crop = int(height * 1.6)
    left = max(0, width // 2 - crop // 2)
    image = image.crop((left, 0, left + crop, height)).resize((640, 400), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def main():
    data = json.loads((CAD / "viewer" / "manifest.json").read_text(encoding="utf-8"))
    models = {}
    for part in data["parts"]:
        mesh = CAD / "viewer" / pathlib.Path(part["file"]).name
        models[part["file"]] = base64.b64encode(mesh.read_bytes()).decode()

    page = (CAD / "viewer_src" / "template.html").read_text(encoding="utf-8")
    page = page.replace("__DATA__", json.dumps(data)).replace("__MODELS__", json.dumps(models)).replace("__PHOTO__", photo_uri())
    head = "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
    (CAD / "block_p_viewer.html").write_text(head + page, encoding="utf-8")
    # An optional second path receives the page without its head, for publishing.
    if len(sys.argv) > 1:
        pathlib.Path(sys.argv[1]).write_text(page, encoding="utf-8")
    print(f"block_p_viewer.html: {len(page) // 1024} KB")


if __name__ == "__main__":
    main()
