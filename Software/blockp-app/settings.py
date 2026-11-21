"""Saved settings. Written atomically (temp file, fsync, rename), so a power cut can't corrupt them."""
import copy, json, os
from pathlib import Path

DATA = Path(os.environ.get("BLOCKP_DATA", Path.home() / "blockp"))
FILE = DATA / "settings.json"

DEFAULTS = {
    "display": {"brightness": 80},
    "audio": {"volume": 18, "muted": False},
    "lights": {"on": True, "mode": "solid", "color": "gold", "brightness": 70, "speed": 1.0},
    "playback": {
        "startup": "idle",            # idle | videos | shuffle_videos | photos
        "slide_seconds": 8,
        "ken_burns": True,            # slow pan and zoom on photos
        "show_titles": True,          # show the title for a few seconds when a video starts
        "idle_style": "animated",     # animated | still
        "idle_clock": False,          # small clock on the idle screen
    },
    "schedule": {"enabled": False, "off": "23:00", "on": "07:00"},
    # Saved light looks: [{"id", "name", "lights": {"on", "mode", "color", "brightness", "speed"}}]
    "presets": [],
    # Scheduled events: [{"id", "enabled", "time": "HH:MM", "days": [0-6, Monday = 0] or "date": "YYYY-MM-DD",
    #                     "action": {"type": ..., "preset": id}}]. One-date events remove themselves once run.
    "events": [],
    "screen": {"rotation": 180, "auto_close": 15},
    "name": "Block P",
}


def _merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif k in out:                       # ignore keys we no longer use
            out[k] = v
    return out


def load() -> dict:
    try:
        return _merge(DEFAULTS, json.loads(FILE.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULTS)


def save(settings: dict):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, FILE)


def patch(settings: dict, changes: dict) -> dict:
    """Apply a partial update, keeping only known keys."""
    return _merge(settings, changes)
