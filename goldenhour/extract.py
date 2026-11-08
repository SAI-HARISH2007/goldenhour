"""Rule-based extraction of a cyber-fraud complaint from a romanized Telugu-English call.

No language model: every field points back to the exact words it came from (`ev`
= character spans in the transcript), so the call-taker can verify each value.
"""
import re
from datetime import datetime, timedelta

ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                   "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
ONES["oh"] = 0
TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
SCALE = {"hundred": 100, "thousand": 1000, "lakh": 100000, "lakhs": 100000, "lac": 100000, "lacs": 100000,
         "crore": 10 ** 7, "crores": 10 ** 7}
TE_DIGITS = {"sunna": 0, "okati": 1, "rendu": 2, "moodu": 3, "naalugu": 4, "aidu": 5, "aaru": 6,
             "edu": 7, "enimidi": 8, "tommidi": 9}
DIGIT = {w: v for w, v in ONES.items() if v < 10} | TE_DIGITS

# romanized spellings of English loanwords Prisma sometimes writes in Telugu script
NORM = {"byaank": "bank", "baank": "bank", "traansaakshan": "transaction", "transaakshan": "transaction",
        "aidi": "id", "ai": "id", "entar": "enter", "kat": "cut", "saar": "sir", "deeteyils": "details",
        "linku": "link", "kaal": "call", "polees": "police", "pin": "pin", "otipi": "otp", "oteepee": "otp",
        "rupees": "rupees", "rs": "rupees", "roopaayalu": "rupees", "rupaayalu": "rupees", "oclock": "oclock"}
SUFFIXES = ("lo", "ki", "ku", "gaa", "ni", "ne", "to")

BANKS = {"sbi": "State Bank of India (SBI)", "state bank": "State Bank of India (SBI)", "hdfc": "HDFC Bank",
         "icici": "ICICI Bank", "axis": "Axis Bank", "canara": "Canara Bank", "kotak": "Kotak Mahindra Bank",
         "pnb": "Punjab National Bank", "punjab national": "Punjab National Bank", "union bank": "Union Bank of India",
         "bank of baroda": "Bank of Baroda", "baroda": "Bank of Baroda", "indian bank": "Indian Bank",
         "idbi": "IDBI Bank", "yes bank": "Yes Bank", "federal": "Federal Bank", "indusind": "IndusInd Bank"}
APPS = {"phonepe": "PhonePe (UPI)", "google pay": "Google Pay (UPI)", "gpay": "Google Pay (UPI)",
        "paytm": "Paytm (UPI)", "bhim": "BHIM (UPI)", "net banking": "Net banking",
        "credit card": "Credit card", "debit card": "Debit card"}
UPI_HANDLES = {"ybl": "PhonePe", "ibl": "PhonePe", "axl": "PhonePe", "okaxis": "Google Pay", "oksbi": "Google Pay",
               "okicici": "Google Pay", "okhdfcbank": "Google Pay", "paytm": "Paytm", "upi": "BHIM"}
RELATIONS = {"naanna": "father", "nanna": "father", "amma": "mother", "tammudu": "younger brother",
             "anna": "elder brother", "akka": "elder sister", "chelli": "younger sister", "bhaarya": "wife",
             "bharta": "husband", "koduku": "son", "kooturu": "daughter", "taatayya": "grandfather",
             "ammamma": "grandmother", "naanamma": "grandmother"}
SCAMS = [  # (label, keywords, advice for the call-taker)
    ("Digital arrest (fake police / CBI)", {"police", "arrest", "cbi", "customs", "warrant", "court", "video",
                                            "courier", "parcel", "narcotics"},
     "Tell the family: real police never arrest anyone over a video call. Check whether more transfers were made."),
    ("Fake customer-care / refund scam", {"customer", "care", "refund", "helpline", "google"},
     "Never enter a UPI PIN to receive money. Block the receiving UPI ID; check for pending collect requests."),
    ("Phishing link (fake KYC / bill)", {"kyc", "link", "sms", "apk", "update", "electricity", "bill"},
     "Card and net-banking details may be stolen: ask the caller to block the card and reset net-banking now."),
    ("OTP fraud", {"otp"}, "Ask which OTPs were shared; block the card / account linked to them."),
    ("Investment / task scam", {"investment", "trading", "task", "telegram", "profit", "stock"},
     "Collect every UPI ID and account the money went to: these scams use many."),
    ("Lottery / prize scam", {"lottery", "prize", "kbc", "gift"}, "Collect the number that called and every payment made."),
]
HEDGE = {"anukuntaa", "anukunta", "emo", "maybe", "approx", "approximately", "teleedu", "teliyadu", "telidu", "around"}
RECEIVED = {"ichchaaru", "ichaaru", "ichcharu", "icchaaru", "ichchindi", "vachchaayi", "received", "credited", "credit"}
DEMANDED = {"adugutunnaru", "adugutunnaaru", "adigaaru", "adiginaaru", "kattamantunnaaru", "kattamannaaru",
            "kattamannaru", "demanding", "asking", "ask"}
NEG = {"ledu", "leedu", "ledhu", "teleedu", "teliyadu", "telidu", "no", "dont"}
DAY = {"ivaala": 0, "eeroju": 0, "eeroja": 0, "today": 0, "ninna": 1, "yesterday": 1, "monna": 2}
PART = {"madhyaahnam": "pm", "afternoon": "pm", "raatri": "pm", "night": "pm", "saayantram": "pm",
        "evening": "pm", "morning": "am", "udayam": "am", "podduna": "am"}
PART_DEFAULT = {"am": 9, "pm": 16}


class Tok:
    def __init__(self, raw, s, e):
        self.raw, self.s, self.e = raw, s, e
        w = NORM.get(raw.lower(), raw.lower())
        self.w = w

    def base(self, vocab):
        if self.w in vocab:
            return self.w
        for suf in SUFFIXES:
            if self.w.endswith(suf) and self.w[: -len(suf)] in vocab:
                return self.w[: -len(suf)]
        return self.w


def tokenize(text):
    return [Tok(m.group(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z0-9]+", text)]


def _num_at(toks, i):
    """Parse an English number phrase at i. Returns (value, next_i) or None."""
    total = cur = 0; j = i; seen = False
    while j < len(toks):
        w = toks[j].w
        if w in ONES: cur += ONES[w]
        elif w in TENS: cur += TENS[w]
        elif w == "hundred" and seen: cur *= 100
        elif w in SCALE and seen: total += max(cur, 1) * SCALE[w]; cur = 0
        elif w == "and" and seen and j + 1 < len(toks) and (toks[j + 1].w in ONES or toks[j + 1].w in TENS): pass
        elif w.isdigit(): cur += int(w)
        else: break
        seen = True; j += 1
    return (total + cur, j) if seen else None


def _digit_run(toks, i):
    """A run of single spoken digits ('four one two three', 'double five'). Returns (str, next_i)."""
    out, j = "", i
    while j < len(toks):
        w = toks[j].w
        if w in ("double", "triple") and j + 1 < len(toks) and toks[j + 1].w in DIGIT:
            out += str(DIGIT[toks[j + 1].w]) * (2 if w == "double" else 3); j += 2
        elif w in DIGIT: out += str(DIGIT[w]); j += 1
        elif w.isdigit() and len(w) <= 4: out += w; j += 1
        else: break
    return out, j


def _near(toks, i, words, ahead=4, behind=0):
    return any(t.w in words or t.base(words) in words for t in toks[max(0, i - behind): i + ahead + 1])


def _phrase(toks, i, phrase):
    ws = phrase.split()
    return all(i + k < len(toks) and toks[i + k].base({ws[k]}) == ws[k] for k in range(len(ws)))


def extract(text, call_time=None):
    call_time = call_time or datetime.now()
    toks = tokenize(text)
    f = {}

    def put(key, value, s, e, note=None, sure=True):
        f.setdefault(key, []).append({"value": value, "ev": [s, e], "note": note, "sure": sure})

    # ---- digit runs (IDs, account numbers, phone numbers) and amounts --------------------
    used = set(); i = 0
    while i < len(toks):
        run, j = _digit_run(toks, i)
        if len(run) >= 6 and not (j < len(toks) and toks[j].w in SCALE):
            ctx = " ".join(t.w for t in toks[max(0, i - 4): i])
            s, e = toks[i].s, toks[j - 1].e
            if re.search(r"transaction|utr|reference|ref", ctx) or (len(run) == 12 and "account" not in ctx):
                ok = len(run) == 12
                put("utr", run, s, e, None if ok else f"{len(run)} digits — UPI/IMPS UTRs are 12. Re-confirm.", ok)
            elif "account" in ctx:
                put("dest_account", run, s, e)
            elif len(run) == 10 and run[0] in "6789":
                put("scam_phone", "+91 " + run, s, e)
            else:
                put("unknown_number", run, s, e, "Number heard but not labelled — ask what it is.", False)
            used.update(range(i, j)); i = j; continue
        n = _num_at(toks, i)
        if n:
            val, j = n
            words = {t.w for t in toks[i:j]}
            money = (j < len(toks) and toks[j].w == "rupees") or words & {"thousand", "lakh", "lakhs", "lac", "crore"}
            if money and val >= 100:
                end = toks[j].e if j < len(toks) and toks[j].w == "rupees" else toks[j - 1].e
                hedged = _near(toks, j, HEDGE, ahead=3)
                after = {t.w for t in toks[j: j + 3]}
                if after & RECEIVED:
                    put("received", val, toks[i].s, end, "Paid BY the scammer to build trust — not a loss.")
                elif after & DEMANDED:
                    put("demanded", val, toks[i].s, end, "Asked for, not yet paid — warn the caller not to pay.")
                else:
                    put("amount", val, toks[i].s, end, "Caller unsure — confirm from bank SMS." if hedged else None, not hedged)
                used.update(range(i, j)); i = j; continue
        i += 1

    # ---- UPI ID: "<name> dot <x> seven at ybl" ------------------------------------------
    for i, t in enumerate(toks):
        if t.w == "at" and i + 1 < len(toks) and 0 < i:
            handle = toks[i + 1].w
            if handle not in UPI_HANDLES and len(handle) > 10:
                continue
            parts, k = [], i - 1
            while k >= 0 and toks[k].w not in ("id", "upi", "is", "ki", "ku", "naa", "account") and i - k <= 6:
                w = toks[k].w
                parts.insert(0, {"dot": ".", "underscore": "_", "hyphen": "-", "dash": "-"}.get(w, str(DIGIT[w]) if w in DIGIT else w))
                k -= 1
            if parts and _near(toks, i, {"upi", "id"}, ahead=0, behind=8):
                vpa = "".join(parts) + "@" + handle
                put("dest_upi", vpa, toks[k + 1].s, toks[i + 1].e,
                    f"Handle @{handle} belongs to {UPI_HANDLES[handle]}" if handle in UPI_HANDLES else None)

    # ---- bank, app, relation, time ------------------------------------------------------
    for i, t in enumerate(toks):
        for key, name in BANKS.items():
            if _phrase(toks, i, key) and not any(x["value"] == name for x in f.get("bank", [])):
                hedged = _near(toks, i, HEDGE, ahead=3)
                put("bank", name, t.s, toks[i + len(key.split()) - 1].e,
                    "Caller unsure — confirm the bank." if hedged else None, not hedged)
        for key, name in APPS.items():
            if _phrase(toks, i, key) and not any(x["value"] == name for x in f.get("app", [])):
                put("app", name, t.s, toks[i + len(key.split()) - 1].e)
        if t.w in RELATIONS and i > 0 and toks[i - 1].w in ("maa", "naa", "ma", "na") and "victim" not in f:
            put("victim", f"Caller's {RELATIONS[t.w]}", toks[i - 1].s, t.e, "Caller is reporting on someone's behalf.")

    # time of fraud
    day = part = None; hour = minute = None; tev = []
    for i, t in enumerate(toks):
        if t.w in DAY and day is None: day = DAY[t.w]; tev.append((t.s, t.e))
        if t.w in PART and part is None: part = PART[t.w]; tev.append((t.s, t.e))
        if t.w in ONES and 1 <= ONES[t.w] <= 12 and hour is None and i not in used:
            nxt = toks[i + 1].w if i + 1 < len(toks) else ""
            nxt2 = toks[i + 2].w if i + 2 < len(toks) else ""
            if nxt in ("oclock", "am", "pm") or (nxt == "o" and nxt2 == "clock"):
                hour, minute = ONES[t.w], 0; tev.append((t.s, toks[i + (2 if nxt == "o" else 1)].e))
                if nxt in ("am", "pm"): part = nxt
            elif nxt in ("thirty", "fifteen", "forty", "ten", "twenty", "five", "fifty") and nxt2 not in SCALE:
                mn = _num_at(toks, i + 1)
                if mn and mn[0] < 60 and (mn[1] >= len(toks) or toks[mn[1]].w not in SCALE):
                    hour, minute = ONES[t.w], mn[0]; tev.append((t.s, toks[mn[1] - 1].e))
    if day is not None or hour is not None:
        d = (call_time - timedelta(days=day or 0)).date()
        exact = hour is not None
        h = hour if exact else PART_DEFAULT.get(part, 12)
        if exact and part == "pm" and h < 12: h += 12
        if exact and part is None and h < 8: h += 12  # "two thirty" with no context: afternoon is likelier
        when = datetime(d.year, d.month, d.day, h, minute or 0)
        label = ["Today", "Yesterday", "Day before yesterday"][day or 0]
        label += f", {when.strftime('%-I:%M %p')}" if exact else (f" {('morning' if part == 'am' else 'afternoon/evening')} — exact time not given" if part else " — time not given")
        s, e = min(x[0] for x in tev), max(x[1] for x in tev)
        put("when", label, s, e, None if exact else "Ask for the exact time (bank SMS shows it).", exact)
        f["_when_dt"] = when.isoformat(); f["_when_exact"] = exact

    # scam type + notable actions
    words = {t.base(set().union(*[k for _, k, _ in SCAMS])) for t in toks}
    best = max(SCAMS, key=lambda s: len(words & s[1]))
    hits = words & best[1]
    if hits:
        spans = [[t.s, t.e] for t in toks if t.base(best[1]) in hits]
        put("scam_type", best[0], 0, 0, "Matched: " + ", ".join(sorted(hits)))
        f["scam_type"][-1]["ev"] = spans  # one highlight per matched word
        f["_advice"] = best[2]
    flags = []
    for i, t in enumerate(toks):
        if t.w == "pin" and _near(toks, i, {"enter"}, ahead=2):
            flags.append(("Victim entered UPI PIN (a PIN only ever sends money)", t.s, toks[min(i + 1, len(toks) - 1)].e))
        if t.w == "link" and _near(toks, i, {"open", "click"}, ahead=2):
            flags.append(("Victim opened a link and entered details", t.s, toks[min(i + 1, len(toks) - 1)].e))
        if t.w in ("rendusaarlu", "twice") or _phrase(toks, i, "two times"):
            flags.append(("More than one debit", t.s, t.e))
        if t.w in ("id", "utr") and _near(toks, i, NEG, ahead=4) and "utr" not in f:
            put("utr", None, t.s, toks[min(i + 4, len(toks) - 1)].e, "Caller doesn't have it.", False)
    f["_flags"] = [{"text": x, "ev": [s, e]} for x, s, e in flags]
    return f


FIELDS = [  # key, label, ask-next (English, romanized Telugu for the call-taker)
    ("victim", "Victim", None),
    ("scam_type", "Scam type", ("What happened, step by step?", "Emi jarigindo modati nundi cheppandi.")),
    ("amount", "Amount lost", ("How much money was debited?", "Entha dabbulu cut ayyaayi?")),
    ("when", "Time of fraud", ("What time was the money debited?", "Dabbulu e time ki cut ayyaayi? Bank SMS lo time chudandi.")),
    ("bank", "Victim's bank", ("Which bank is the account in?", "Account e bank lo undi?")),
    ("app", "Payment mode", ("Which app or method was used?", "PhonePe, Google Pay, leka net banking?")),
    ("utr", "Transaction ID (UTR)", ("Read the 12-digit UTR from the bank SMS.", "Bank SMS lo 12 ankela UTR number untundi, adi cheppandi.")),
    ("dest_upi", "Money sent to (UPI ID)", ("Which UPI ID or account did the money go to?", "Dabbulu e UPI ID ki leka e account ki vellaayi?")),
    ("dest_account", "Money sent to (account)", None),
    ("received", "Money received from scammer", None),
    ("demanded", "Scammer is still demanding", None),
    ("scam_phone", "Scammer's number", ("Which number called you?", "Meeku e number nundi call vachchindi?")),
]
REQUIRED = ["scam_type", "amount", "when", "bank", "utr", "dest_upi"]


def complaint(text, call_time=None):
    call_time = call_time or datetime.now()
    f = extract(text, call_time)
    rows, ask = [], []
    has_dest = "dest_upi" in f or "dest_account" in f
    for key, label, q in FIELDS:
        items = [x for x in f.get(key, []) if x["value"] is not None]
        if key == "victim" and not items:
            rows.append({"key": key, "label": label, "items": [{"value": "Caller (self)", "ev": None, "note": None, "sure": True}]})
            continue
        if key in ("dest_account", "received", "demanded") and not items:
            continue
        missing = not items and not (key == "dest_upi" and has_dest)
        unsure = [x for x in items if not x["sure"]]
        note = next((x["note"] for x in f.get(key, []) if x["value"] is None), None)
        rows.append({"key": key, "label": label, "items": items, "missing": missing, "note": note})
        if q and (missing and (key in REQUIRED or key == "scam_phone") or unsure):
            ask.append({"field": label, "en": q[0], "te": q[1], "why": "missing" if missing else "unconfirmed"})
    amounts = [x["value"] for x in f.get("amount", [])]
    total = sum(amounts)
    hours = None
    if "_when_dt" in f:
        hours = round((call_time - datetime.fromisoformat(f["_when_dt"])).total_seconds() / 3600, 1)
    filled = sum(1 for r in rows if r.get("items") and not r.get("missing") and r["key"] not in ("victim", "received", "demanded"))
    return {"rows": rows, "ask": ask, "flags": f["_flags"], "advice": f.get("_advice"),
            "total": total, "n_debits": len(amounts), "hours_since": hours, "when_exact": f.get("_when_exact"),
            "filled": filled, "required_missing": [a["field"] for a in ask if a["why"] == "missing"]}
