# GoldenHour: the victim's call becomes the fraud complaint

*Solution pitch for Gnani AI's Great Indian AI Internship Challenge. Sai Haresh Anand S, IFHE Hyderabad.*

**Problem.** When someone in India loses money to a UPI scam, they call the 1930 cyber-fraud helpline. The first hours decide whether the money can be frozen before it moves on. During that call, the call-taker types the amount, time, bank, payment app, transaction ID, destination UPI ID and the scammer's number by hand, while the caller panics, often mixing Telugu and English.

**Solution.** GoldenHour is a co-pilot for the call-taker. It listens to the call and fills the complaint in about half a second after transcription:
- **Eight complaint fields**: amount, time of fraud, bank, payment app, UTR, destination UPI ID or account, scammer's number, scam type (e.g. "digital arrest", fake KYC, fake refund).
- **Evidence for every field.** Each value is linked to the exact words in the transcript it came from.
- **It never guesses.** Hedged or unclear values are marked "confirm", and the call-taker is told to read them back.
- **What to ask next.** Missing fields become ready-to-say questions in English and romanized Telugu.
- **Urgency and handoff.** Time since the fraud, plus a draft complaint to paste into the reporting portal.

**How it works.**
1. **Gnani AI Prisma v3.0** speech-to-text (`te-IN`, code-mix output) handles Telugu-English mixing in one pass. Audio longer than 30 s is split at a natural pause.
2. Telugu script is romanized so the rules work on one alphabet.
3. **Rule-based extraction, no LLM, by design.** A complaint that may go to police must be traceable to what the caller said, and the system must refuse to invent a value.

**Results so far.** Tested on four role-play calls recorded by me and a friend (no real victim data). On the call in the video, 6 of 8 fields filled from a 15-second call, speech-to-text took 534 ms, and the two missing fields (UTR, scammer's number) became questions for the caller.

**Limits and next steps.** Not yet tested on real helpline audio; the rules cover common scam patterns in Telugu and English only. Next: streaming STT during the call, more Indian languages (Prisma supports them), and a pilot conversation with a bank fraud desk or a cyber cell.

**Run it:** see [README.md](README.md). The demo calls and their cached transcripts are in the repo, so the demo runs with zero API credits.
