"""Download a video (YouTube or any site yt-dlp supports) into the sign's library, once, so playback
never depends on the internet. Saves <library>/videos/<id>.mp4, <id>.jpg and <id>.json.

Command line:  python downloader.py <url> [--title "2023 Halftime"] [--year 2023] [--clip 0-30]
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

import yt_dlp

LIBRARY = Path(os.environ.get("BLOCKP_LIBRARY", Path.home() / "blockp" / "library"))
VIDEOS = LIBRARY / "videos"


def write_json_atomic(path: Path, data: dict):
    """Write to a temp file, flush it to the card, then rename: a power cut leaves the old or the new file, never half of one."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def probe(video: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=codec_name,width,height,r_frame_rate:format=duration", "-of", "json", str(video)],
                         capture_output=True, text=True).stdout
    d = json.loads(out or "{}")
    s = (d.get("streams") or [{}])[0]
    num, _, den = (s.get("r_frame_rate") or "0/1").partition("/")
    return {"codec": s.get("codec_name"), "width": s.get("width") or 0, "height": s.get("height") or 0,
            "fps": float(num) / float(den or 1), "duration": float(d.get("format", {}).get("duration") or 0)}


def needs_optimizing(video: Path) -> bool:
    p = probe(video)
    return p["codec"] != "h264" or p["height"] > 720 or p["fps"] > 31


def optimize(video: Path, progress=None):
    """Re-encode to H.264 720p at 30 fps (once, after download). Uses the Pi's hardware encoder,
    falling back to software. Writes a temp file and renames it, so a power cut keeps the original."""
    p = probe(video)
    tmp = video.with_suffix(".opt.mp4")
    vf = "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30"
    for enc in (["-c:v", "h264_v4l2m2m", "-b:v", "5M", "-pix_fmt", "yuv420p"],
                ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-profile:v", "high", "-pix_fmt", "yuv420p"]):
        cmd = ["ffmpeg", "-y", "-v", "error", "-progress", "pipe:1", "-i", str(video), "-vf", vf, *enc,
               "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(tmp)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        for line in proc.stdout:
            if line.startswith("out_time_us=") and progress and p["duration"]:
                us = line.split("=")[1].strip()
                if us.isdigit():
                    progress(min(1.0, int(us) / 1e6 / p["duration"]), "optimizing")
        if proc.wait() == 0 and tmp.exists() and probe(tmp)["height"] > 0:
            os.replace(tmp, video)
            return
        tmp.unlink(missing_ok=True)
    raise RuntimeError("could not convert the video for smooth playback")


def download(url: str, title: str | None = None, year: int | None = None, clip: str | None = None,
             progress=None) -> dict:
    """Download url and return its library entry. progress(fraction 0..1, status text) is called as it goes."""
    VIDEOS.mkdir(parents=True, exist_ok=True)

    def hook(d):
        if not progress:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            progress(d.get("downloaded_bytes", 0) / total if total else 0.0, "downloading")
        elif d["status"] == "finished":
            progress(1.0, "processing")

    opts = {
        "outtmpl": str(VIDEOS / "%(id)s.%(ext)s"),
        # H.264 + AAC, 720p at 30 fps: tested on the Pi to play with zero dropped frames under the
        # frosted-glass menu (1080p60 dropped over half). The screen is 1280x800, so 720p loses nothing.
        "format": "bv*[vcodec^=avc1][height<=720][fps<=30]+ba[acodec^=mp4a]/bv*[vcodec^=avc1][height<=720]+ba[acodec^=mp4a]"
                  "/bv*[height<=720]+ba/b[height<=720]/b",
        "format_sort": ["vcodec:h264", "res:720", "fps:30", "acodec:aac"],
        "merge_output_format": "mp4",
        "writethumbnail": True,
        "postprocessors": [{"key": "FFmpegThumbnailsConvertor", "format": "jpg"}],
        "js_runtimes": {"node": {}},
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }
    if clip:                                   # e.g. "0-30" seconds, handy for testing
        start, end = (float(x) for x in clip.split("-"))
        opts["download_ranges"] = yt_dlp.utils.download_range_func(None, [(start, end)])
        opts["force_keyframes_at_cuts"] = True

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    vid = info["id"]
    video = VIDEOS / f"{vid}.mp4"
    if not video.exists():
        raise RuntimeError(f"download finished but {video.name} is missing")
    if needs_optimizing(video):
        if progress:
            progress(0.0, "optimizing")
        optimize(video, progress)
    upload = info.get("upload_date") or ""
    entry = {
        "id": vid,
        "title": title or info.get("title") or vid,
        "year": year or (int(upload[:4]) if re.fullmatch(r"\d{8}", upload) else None),
        "duration": info.get("duration") if not clip else None,
        "source": url,
        "uploader": info.get("uploader"),
        "added": time.strftime("%Y-%m-%d %H:%M"),
        "video": video.name,
        "thumb": f"{vid}.jpg" if (VIDEOS / f"{vid}.jpg").exists() else None,
    }
    final = probe(video)
    entry.update({"codec": final["codec"], "height": final["height"], "fps": round(final["fps"], 2),
                  "duration": round(final["duration"], 1)})
    write_json_atomic(VIDEOS / f"{vid}.json", entry)
    return entry


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--title")
    ap.add_argument("--year", type=int)
    ap.add_argument("--clip", help="only download this many seconds, e.g. 0-30")
    a = ap.parse_args()
    last = [-1]
    def show(frac, status):
        pct = int(frac * 100)
        if pct >= last[0] + 10 or status != "downloading":
            last[0] = pct
            print(f"  {status} {pct}%", flush=True)
    e = download(a.url, a.title, a.year, a.clip, show)
    print(json.dumps(e, indent=2))
