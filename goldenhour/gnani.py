"""Gnani Prisma STT client with an on-disk cache (never pay twice for the same audio).

Prisma accepts at most 30 s per request, so longer audio is split at the quietest
point near the limit and the transcripts are joined.
"""
import hashlib, json, os, pathlib, re, subprocess, tempfile, time, requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
BASE = "https://api.vachana.ai"
MAX_S = 28.0


def _key():
    k = os.environ.get("GNANI_API_KEY")
    if not k:
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("GNANI_API_KEY="):
                k = line.split("=", 1)[1].strip()
    if not k:
        raise RuntimeError("GNANI_API_KEY missing from .env")
    return k


def _stt_one(audio: bytes, name: str, fmt: str, language_code: str, model: str):
    params = {"language_code": language_code, "format": fmt, "model": model}
    CACHE.mkdir(exist_ok=True)
    cp = CACHE / f"stt-{hashlib.sha256(json.dumps(params, sort_keys=True).encode() + audio).hexdigest()[:20]}.json"
    if cp.exists():
        body = json.loads(cp.read_text(encoding="utf-8")); body["_cached"] = True
        return body
    r = requests.post(f"{BASE}/stt/v3", headers={"X-API-Key-ID": _key()}, data=params,
                      files={"audio_file": (name, audio)}, timeout=90)
    body = r.json()
    if r.status_code != 200 or not body.get("success"):
        raise RuntimeError(f"STT failed {r.status_code}: {body}")
    cp.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    body["_cached"] = False
    return body


def duration(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def _split_points(path, total):
    """Cut points (s): the middle of a silence closest to (but under) MAX_S after the last cut."""
    log = subprocess.run(["ffmpeg", "-i", str(path), "-af", "silencedetect=n=-35dB:d=0.25",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    mids = [(s + e) / 2 for s, e in zip(starts, ends)]
    cuts, last = [], 0.0
    while total - last > MAX_S:
        ok = [m for m in mids if last + 5 < m <= last + MAX_S]
        cut = max(ok) if ok else last + MAX_S
        cuts.append(cut); last = cut
    return cuts


def stt(audio_path, fmt="codemix", language_code="te-IN", model="prisma-v3.0"):
    """Returns {"transcript", "latency_ms", "cached", "chunks"}."""
    path = pathlib.Path(audio_path)
    total = duration(path)
    if total <= 29.5:
        b = _stt_one(path.read_bytes(), path.name, fmt, language_code, model)
        return {"transcript": b["transcript"], "latency_ms": int(b.get("end_to_end_latency", 0) * 1000),
                "cached": b["_cached"], "chunks": 1}
    bounds = [0.0] + _split_points(path, total) + [total]
    texts, lat, cached = [], 0, True
    with tempfile.TemporaryDirectory() as td:
        for i, (s, e) in enumerate(zip(bounds, bounds[1:])):
            part = pathlib.Path(td) / f"{path.stem}_{i}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ss", f"{s:.3f}", "-to", f"{e:.3f}",
                            "-ac", "1", "-ar", "16000", str(part)], check=True)
            b = _stt_one(part.read_bytes(), part.name, fmt, language_code, model)
            texts.append(b["transcript"]); lat += int(b.get("end_to_end_latency", 0) * 1000)
            cached = cached and b["_cached"]
    return {"transcript": " ".join(texts), "latency_ms": lat, "cached": cached, "chunks": len(texts)}
