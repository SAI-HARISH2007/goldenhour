"""Deterministic Telugu-script -> readable Latin ("Tenglish") converter.
Used only for display and for the cleaner's matching; never sent to TTS."""

V = {"అ": "a", "ఆ": "aa", "ఇ": "i", "ఈ": "ee", "ఉ": "u", "ఊ": "oo", "ఋ": "ru",
     "ఎ": "e", "ఏ": "e", "ఐ": "ai", "ఒ": "o", "ఓ": "o", "ఔ": "au"}
SIGN = {"ా": "aa", "ి": "i", "ీ": "ee", "ు": "u", "ూ": "oo", "ృ": "ru",
        "ె": "e", "ే": "e", "ై": "ai", "ొ": "o", "ో": "o", "ౌ": "au"}
C = {"క": "k", "ఖ": "kh", "గ": "g", "ఘ": "gh", "ఙ": "n", "చ": "ch", "ఛ": "chh",
     "జ": "j", "ఝ": "jh", "ఞ": "n", "ట": "t", "ఠ": "th", "డ": "d", "ఢ": "dh",
     "ణ": "n", "త": "t", "థ": "th", "ద": "d", "ధ": "dh", "న": "n", "ప": "p",
     "ఫ": "ph", "బ": "b", "భ": "bh", "మ": "m", "య": "y", "ర": "r", "ల": "l",
     "వ": "v", "శ": "sh", "ష": "sh", "స": "s", "హ": "h", "ళ": "l", "ఱ": "r"}
VIRAMA, ANUSVARA, VISARGA, CANDRA = "్", "ం", "ః", "ఁ"
DIGITS = {chr(0x0C66 + i): str(i) for i in range(10)}


def romanize(text):
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if ch in C:
            out.append(C[ch])
            if nxt in SIGN:
                out.append(SIGN[nxt]); i += 1
            elif nxt == VIRAMA:
                i += 1
            else:
                out.append("a")
        elif ch in V:
            out.append(V[ch])
        elif ch == ANUSVARA:
            following = text[i + 1:i + 2]
            out.append("m" if following in ("ప", "బ", "మ", "ఫ", "భ", "") or not following.strip() else "n")
        elif ch in (VISARGA,):
            out.append("h")
        elif ch == CANDRA:
            out.append("n")
        elif ch in DIGITS:
            out.append(DIGITS[ch])
        elif ch in SIGN or ch == VIRAMA:
            pass  # stray mark
        else:
            out.append(ch)
        i += 1
    return "".join(out)
