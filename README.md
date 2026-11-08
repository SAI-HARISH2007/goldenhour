# GoldenHour

Co-pilot for India's **1930 cyber-fraud helpline**. A panicked victim's call (Telugu + English, code-mixed) becomes a filled fraud complaint in under a second: amount lost, time, bank, UPI app, transaction ID (UTR), destination UPI ID / account, scammer's phone, and scam type. Every field is linked to the exact words it came from. Missing or uncertain fields become "ask the caller next" prompts, in English and romanized Telugu.

Built for Gnani AI's **Great Indian AI Internship Challenge 2026**.

> The demo calls are role-plays recorded by the builder. No real victim data.

## How it works
1. **Speech to text:** Gnani **Prisma v3.0** (`/stt/v3`, `language_code=te-IN`, `format=codemix`). Audio over 30 s is split at a silence near 28 s.
2. **Romanize:** Telugu script is converted to Latin letters (`goldenhour/romanize.py`).
3. **Extract:** rule-based, with **no language model** (`goldenhour/extract.py`). It never guesses. Hedged values ("approx", "I think") are marked *confirm*.

Every STT response is cached in `.cache/`, keyed by the audio bytes, so the same audio is never paid for twice. The three demo calls are already cached, so they cost **zero credits**.

## Run
```bash
sudo apt install ffmpeg          # needs ffmpeg + ffprobe
pip install -r requirements.txt
echo "GNANI_API_KEY=..." > .env  # only needed for NEW audio (live calls)
python3 server.py                # open http://localhost:5000
```

## Layout
| File | What |
|---|---|
| `server.py` | Flask app: `/api/sample/<fraud1-3>`, `/api/process` (live mic) |
| `goldenhour/gnani.py` | Prisma client, chunking, cache |
| `goldenhour/extract.py` | Field extraction, scam types, ask-next questions, draft complaint |
| `static/index.html` | The whole UI (one file) |
