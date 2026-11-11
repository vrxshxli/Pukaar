"""Compare family names written in Devanagari or Latin letters.

Families get reported as "Patil family", "पाटिल परिवार" and "पाटील कुटुंब".
We reduce each name to a rough consonant skeleton ("ptl") so the spellings can
be compared. It is deliberately simple; it only needs to tell names apart.
"""
from rapidfuzz import fuzz

CONSONANTS = {
    "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n", "च": "ch", "छ": "ch", "ज": "j", "झ": "j", "ञ": "n",
    "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n", "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "b", "म": "m", "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h", "क़": "k", "ख़": "k", "ग़": "g", "ज़": "z", "ड़": "d", "फ़": "f",
    "ं": "n", "ँ": "n",
}
VOWELS = set("aeiou")
LATIN_FOLD = [("w", "v"), ("ph", "f"), ("bh", "b"), ("dh", "d"), ("th", "t"), ("kh", "k"), ("gh", "g"),
              ("jh", "j"), ("q", "k"), ("x", "ks"), ("z", "j"), ("c", "k"), ("kh", "k")]


def skeleton(name):
    """'Patil' and 'पाटिल' both become 'ptl'."""
    out = []
    for ch in name.lower():
        if ch in CONSONANTS:
            out.append(CONSONANTS[ch])
        elif "a" <= ch <= "z" and ch not in VOWELS and ch != "y" or ch == "y" and not out:
            out.append(ch)
    text = "".join(out)
    for a, b in LATIN_FOLD:
        text = text.replace(a, b)
    text = text.replace("chh", "ch").replace("sh", "s").replace("ch", "c")
    # Collapse doubled letters: "Bhatt" and "भट्ट" both end up as "bt".
    collapsed = []
    for ch in text:
        if not collapsed or collapsed[-1] != ch:
            collapsed.append(ch)
    return "".join(collapsed).replace("h", "") or text


def same_name_score(a, b):
    """0 to 100: how alike two family names are, across scripts."""
    sa, sb = skeleton(a), skeleton(b)
    if not sa or not sb:
        return None
    return max(fuzz.ratio(sa, sb), fuzz.token_set_ratio(a.lower(), b.lower()))
