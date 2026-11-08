"""GoldenHour demo server. Run: python3 server.py  then open http://localhost:5000"""
import os, pathlib, subprocess, time, uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from goldenhour import gnani
from goldenhour.romanize import romanize
from goldenhour.extract import complaint

ROOT = pathlib.Path(__file__).resolve().parent
REC = ROOT / "recordings"; REC.mkdir(exist_ok=True)
SAMPLES = {"fraud1": "fraud1.m4a", "fraud2": "fraud2.m4a", "fraud3": "fraud3.m4a"}
app = Flask(__name__, static_folder="static")


def run(path: pathlib.Path, call_time: datetime):
    stt = gnani.stt(path, fmt="codemix")
    t0 = time.perf_counter()
    text = romanize(stt["transcript"])
    c = complaint(text, call_time)
    c.update(transcript=text, stt_ms=stt["latency_ms"], cached=stt["cached"], chunks=stt["chunks"],
             build_ms=round((time.perf_counter() - t0) * 1000, 1), seconds=round(gnani.duration(path), 1),
             call_time=call_time.strftime("%-I:%M %p, %d %b"))
    return c


@app.post("/api/sample/<name>")
def api_sample(name):
    if name not in SAMPLES:
        return jsonify(error="unknown sample"), 404
    p = ROOT / SAMPLES[name]
    try:  # the call "happened" when it was recorded
        return jsonify(run(p, datetime.fromtimestamp(os.path.getmtime(p))) | {"audio": f"/clip/{name}"})
    except Exception as e:
        return jsonify(error=str(e)[:300]), 500


@app.post("/api/process")
def api_process():
    f = request.files.get("audio")
    if not f:
        return jsonify(error="no audio"), 400
    ext = pathlib.Path(f.filename or "").suffix.lower()
    ext = ext if ext in {".webm", ".ogg", ".opus", ".m4a", ".mp3", ".wav", ".aac", ".mp4", ".amr", ".flac"} else ".webm"
    src = REC / f"{time.strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}{ext}"
    f.save(src)
    wav = src.with_name(src.stem + "-16k.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", "58", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    try:
        return jsonify(run(wav, datetime.now()))
    except Exception as e:
        return jsonify(error=str(e)[:300]), 500


@app.get("/clip/<name>")
def clip(name):
    if name not in SAMPLES:
        return "", 404
    return send_from_directory(ROOT, SAMPLES[name])


@app.get("/")
def index():
    return send_from_directory(ROOT / "static", "index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
