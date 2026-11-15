"""The sign's media library on the SD card:
    library/videos/<id>.mp4 + <id>.jpg + <id>.json   (made by downloader.py)
    library/photos/<album>/<photo>.jpg               (any album folder name)
    library/cache/                                   (resized photos, rebuilt if deleted)
Phone photos are often 4000 px wide, so each one gets a screen-sized copy and a thumbnail."""
import json, os
from pathlib import Path

from PIL import Image, ImageOps

LIBRARY = Path(os.environ.get("BLOCKP_LIBRARY", Path.home() / "blockp" / "library"))
VIDEOS, PHOTOS, CACHE = LIBRARY / "videos", LIBRARY / "photos", LIBRARY / "cache"
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
SCREEN_MAX, THUMB_MAX = (1600, 1000), (480, 300)


def videos() -> list[dict]:
    out = []
    for f in sorted(VIDEOS.glob("*.json")):
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (VIDEOS / e.get("video", "")).exists():
            e["url"] = f"/media/videos/{e['video']}"
            e["thumb_url"] = f"/media/videos/{e['thumb']}" if e.get("thumb") else None
            out.append(e)
    out.sort(key=lambda e: (-(e.get("year") or 0), e.get("title", "").lower()))
    return out


def _cached(photo: Path, kind: str, size) -> str:
    rel = photo.relative_to(PHOTOS)
    dest = CACHE / kind / rel.with_suffix(".jpg")
    if not dest.exists() or dest.stat().st_mtime < photo.stat().st_mtime:
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
        im.thumbnail(size, Image.LANCZOS)
        tmp = dest.with_suffix(".tmp")
        im.save(tmp, "JPEG", quality=88)
        os.replace(tmp, dest)
    return "/media/cache/" + dest.relative_to(CACHE).as_posix()


def albums() -> list[dict]:
    out = []
    if not PHOTOS.exists():
        return out
    for d in sorted(p for p in PHOTOS.iterdir() if p.is_dir()):
        photos = sorted(p for p in d.iterdir() if p.suffix.lower() in PHOTO_EXT)
        if not photos:
            continue
        items = []
        for p in photos:
            try:
                items.append({"id": f"{d.name}/{p.name}", "url": _cached(p, "screen", SCREEN_MAX),
                              "thumb_url": _cached(p, "thumb", THUMB_MAX)})
            except Exception as e:
                print("skipping photo", p, e, flush=True)
        out.append({"name": d.name, "count": len(items), "cover": items[0]["thumb_url"] if items else None,
                    "photos": items})
    return out


def scan() -> dict:
    return {"videos": videos(), "albums": albums()}


def edit_video(vid: str, title=None, year=None):
    f = VIDEOS / f"{vid}.json"
    e = json.loads(f.read_text(encoding="utf-8"))
    if title is not None:
        e["title"] = str(title)[:120]
    if year is not None:
        e["year"] = int(year) if str(year).strip() else None
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(e, indent=2), encoding="utf-8")
    os.replace(tmp, f)


def delete_video(vid: str):
    for ext in (".mp4", ".jpg", ".json"):
        p = VIDEOS / f"{vid}{ext}"
        if p.exists() and p.parent == VIDEOS:
            p.unlink()


def save_upload(album: str, filename: str, data: bytes) -> str:
    safe_album = "".join(c for c in album if c.isalnum() or c in " -_").strip() or "Photos"
    safe_name = "".join(c for c in Path(filename).name if c.isalnum() or c in ".-_ ").strip() or "photo.jpg"
    if Path(safe_name).suffix.lower() not in PHOTO_EXT:
        raise ValueError("not a photo")
    d = PHOTOS / safe_album
    d.mkdir(parents=True, exist_ok=True)
    dest = d / safe_name
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest)
    return f"{safe_album}/{safe_name}"
