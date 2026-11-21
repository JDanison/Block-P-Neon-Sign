"""Light presets and scheduled events: validation and "what's due now". Pure functions, so the rules
can be checked without the server; server.py stores them in settings and runs the actions."""
import re, secrets, time
from datetime import date, datetime

ACTIONS = ("preset", "lights_on", "lights_off", "sleep", "wake", "videos", "shuffle", "photos", "idle")
LIGHT_KEYS = ("on", "mode", "color", "brightness", "speed")
MAX_PRESETS, MAX_EVENTS = 24, 60
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def new_id(prefix):
    # time plus random: two saves in the same millisecond (two phones, or quick taps) must not collide
    return f"{prefix}{int(time.time() * 1000)}{secrets.token_hex(4)}"


def clean_name(name, fallback):
    name = " ".join(str(name or "").split())[:40]
    return name or fallback


def make_preset(presets, lights, name=None):
    """A preset from the current lights (always saved as on: a preset is a look to switch to)."""
    used = {p["name"] for p in presets}
    n = len(presets) + 1
    while f"Preset {n}" in used:
        n += 1
    snap = {k: lights[k] for k in LIGHT_KEYS if k in lights}
    snap["on"] = True
    return {"id": new_id("p"), "name": clean_name(name, f"Preset {n}"), "lights": snap}


def clean_event(e, presets):
    """A checked copy of an event from a client, or None if it can't run."""
    t = str(e.get("time", ""))
    if not _TIME.match(t):
        return None
    a = e.get("action") or {}
    if a.get("type") not in ACTIONS:
        return None
    action = {"type": a["type"]}
    if a["type"] == "preset":
        if not any(p["id"] == a.get("preset") for p in presets):
            return None
        action["preset"] = a["preset"]
    out = {"id": str(e.get("id") or new_id("e")), "enabled": bool(e.get("enabled", True)), "time": t, "action": action}
    if e.get("date"):
        try:
            out["date"] = date.fromisoformat(str(e["date"])).isoformat()
        except ValueError:
            return None
    else:
        days = sorted({int(d) for d in e.get("days", []) if str(d).lstrip("-").isdigit() and 0 <= int(d) <= 6})
        if not days:
            return None
        out["days"] = days
    return out


def due(events, now: datetime):
    """Enabled events set for this minute: one-date events on today's date, repeating ones on today's weekday."""
    hhmm, today, wd = now.strftime("%H:%M"), now.date().isoformat(), now.weekday()
    return [e for e in events if e.get("enabled", True) and e["time"] == hhmm
            and (e["date"] == today if e.get("date") else wd in e.get("days", []))]
