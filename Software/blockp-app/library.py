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
            e.setdefault("rotation", True)           # in "Play all" and startup playback
            e.setdefault("order", 0)
            out.append(e)
    # Newest season first; within a season, your own order (Edit mode arrows), then title
    out.sort(key=lambda e: (-(e.get("year") or 0), e.get("order", 0), e.get("title", "").lower()))
    return out


def _write_entry(vid: str, e: dict):
    f = VIDEOS / f"{vid}.json"
    clean = {k: v for k, v in e.items() if k not in ("url", "thumb_url")}
    tmp = f.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, f)


def set_rotation(vid: str, on: bool):
    e = json.loads((VIDEOS / f"{vid}.json").read_text(encoding="utf-8"))
    e["rotation"] = bool(on)
    _write_entry(vid, e)


def move_video(vid: str, delta: int):
    """Move a video up (-1) or down (+1) within its season, renumbering that season's order."""
    vids = videos()
    me = next((v for v in vids if v["id"] == vid), None)
    if not me:
        return
    season = [v for v in vids if v.get("year") == me.get("year")]
    i = season.index(me)
    j = max(0, min(len(season) - 1, i + delta))
    season.insert(j, season.pop(i))
    for n, v in enumerate(season):
        if v.get("order") != n:
            v["order"] = n
            _write_entry(v["id"], v)


def _inside(base: Path, p: Path) -> bool:
    """True if p is inside base after resolving '..' and links: deletes never reach outside the library."""
    try:
        p.resolve().relative_to(base.resolve())
        return p.resolve() != base.resolve()
    except ValueError:
        return False


def delete_photo(photo_id: str):
    p = PHOTOS / photo_id
    if not _inside(PHOTOS, p) or not p.is_file():
        raise ValueError("not a photo in the library")
    p.unlink()
    for kind in ("screen", "thumb"):
        c = CACHE / kind / Path(photo_id).with_suffix(".jpg")
        if _inside(CACHE, c) and c.exists():
            c.unlink()
    if not any(p.parent.iterdir()):             # remove the album folder once it's empty
        p.parent.rmdir()


def delete_album(name: str):
    import shutil
    d = PHOTOS / name
    if not _inside(PHOTOS, d) or not d.is_dir() or d.parent.resolve() != PHOTOS.resolve():
        raise ValueError("not an album")
    shutil.rmtree(d)
    for kind in ("screen", "thumb"):
        c = CACHE / kind / name
        if _inside(CACHE, c) and c.is_dir():
            shutil.rmtree(c)


def rename_album(name: str, new: str):
    new = "".join(ch for ch in new if ch.isalnum() or ch in " -_").strip()
    src, dst = PHOTOS / name, PHOTOS / new
    if not new or not _inside(PHOTOS, src) or not src.is_dir() or dst.exists():
        raise ValueError("can't rename to that")
    src.rename(dst)
    for kind in ("screen", "thumb"):                # move the resized copies too, so nothing is rebuilt
        c = CACHE / kind / name
        if c.is_dir():
            c.rename(CACHE / kind / new)


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


def edit_video(vid: str, title=None, year=None, order=None):
    f = VIDEOS / f"{vid}.json"
    e = json.loads(f.read_text(encoding="utf-8"))
    if title is not None:
        e["title"] = str(title)[:120]
    if year is not None:
        e["year"] = int(year) if str(year).strip() else None
    if order is not None:
        e["order"] = int(order)
    _write_entry(vid, e)


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
