"""Rules-mode language detection and report extraction.

This is the deterministic path that always works without a model. It reads
Hindi and Marathi in Devanagari, Hinglish in Latin script, and English.
"""
import re

from rapidfuzz import fuzz

from . import scenario
from .tools import geo

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

MARATHI_MARKERS = ["आहे", "आहेत", "आम्ही", "पाणी", "नाही", "मध्ये", "घरात", "लवकर", "करा", "झाले",
                   "आमच्या", "माझे", "माझी", "आजी", "गल्ली", "वाढत", "हवी", "हवे", "मदत करा", "कृपया मदत",
                   "आहोत", "इथे", "काय करू", "धरण", "जवळ"]
HINDI_MARKERS = ["है", "हैं", "में", "नहीं", "पानी", "हम", "गया", "गई", "के", "की", "रहा", "रही",
                 "बचाओ", "मदद", "गली", "बुखार", "पोते", "दादी", "क्या", "करें", "कृपया"]
HINGLISH_MARKERS = ["hai", "hain", "ke", "ki", "ka", "paani", "pani", "gali", "mandir", "bachcha", "bacche",
                    "madad", "phase", "phanse", "ghar", "log", "hum", "nahi", "jaldi", "bhai", "budhi",
                    "amma", "kya", "karu", "karein", "aa gaya", "raha", "rahi", "bachao", "mein", "tak",
                    "peeche", "paas", "kab", "aayega", "chahiye", "khana", "dudh", "bijli", "batti"]

NUM_WORDS = dict(geo.NUMBER_WORDS)
NUM_WORDS.update({"ten": 10, "das": 10, "दस": 10, "दहा": 10, "a couple": 2, "couple": 2})

PEOPLE_NOUNS = (r"(?:people|persons|members|of us|log|logo|jan|jane|लोग|लोक|जण|जन|सदस्य|family members)")

VULNERABLE = {
    "elderly": ["old", "elderly", "grandmother", "grandfather", "grandma", "granny", "amma", "budhi", "budha",
                "dadi", "nani", "dada", "aaji", "aajoba", "senior", "बुज़ुर्ग", "बुजुर्ग", "बूढ़ी", "बूढ़े", "दादी",
                "नानी", "आजी", "आजोबा", "वृद्ध", "bedridden", "lives alone", "akele", "अकेले", "एकटे", "एकट्या"],
    "child": ["child", "children", "baby", "kid", "kids", "infant", "toddler", "bachcha", "bachche", "bacche",
              "bachi", "pota", "pote", "grandson", "granddaughter", "बच्चा", "बच्चे", "बच्ची", "पोता", "पोते",
              "मुलगा", "मुलगी", "बाळ", "लहान मूल", "मुले", "small kid", "chhota"],
    "pregnant": ["pregnant", "garbhvati", "pregnent", "गर्भवती", "गरोदर", "delivery"],
    "disabled": ["wheelchair", "disabled", "handicap", "viklang", "विकलांग", "अपंग", "can't walk", "cannot walk",
                 "chal nahi", "चल नहीं", "बिस्तर पर", "paralysed", "paralyzed"],
}
MEDICAL = {
    "unconscious": ["unconscious", "fainted", "not waking", "behosh", "बेहोश", "बेशुद्ध", "not responding"],
    "breathing": ["can't breathe", "cannot breathe", "breathing problem", "saans", "सांस", "श्वास", "asthma"],
    "injured": ["injured", "injury", "bleeding", "blood", "chot", "ghayal", "घायल", "चोट", "जखमी", "fracture", "broken leg"],
    "fever": ["fever", "bukhar", "bukhaar", "बुखार", "ताप", "high temperature"],
    "dialysis": ["dialysis", "डायलिसिस"],
    "chronic": ["diabetes", "diabetic", "insulin", "heart patient", "bp patient", "sugar patient", "oxygen"],
}
DANGER = {
    "gas": ["gas", "lpg", "cylinder leak", "गैस", "गॅस", "badbu", "बदबू", "वास येत"],
    "fire": ["fire", "aag", "आग", "smoke", "dhuan", "धुआँ", "धुआं", "धूर"],
    "electrical": ["current", "karant", "करंट", "shock", "wire", "taar", "तार", "spark", "transformer",
                   "ट्रान्सफॉर्मर", "बिजली का तार", "वीज"],
}
WATER_LEVELS = [
    ("roof", ["roof", "terrace", "chhat par", "chhat pe", "chat par", "छत", "छतावर", "on top of the house"]),
    ("neck", ["neck", "gale tak", "गले तक", "गळ्यापर्यंत"]),
    ("chest", ["chest", "seene", "chhati", "छाती", "सीने"]),
    ("waist", ["waist", "kamar", "कमर", "कंबर"]),
    ("knee", ["knee", "ghutno", "ghutne", "घुटनों", "घुटने", "गुडघ"]),
    ("ankle", ["ankle", "takhne", "टखने", "घोट्या"]),
    ("entering", ["water entering", "water is entering", "entering the house", "water inside", "inside the house",
                  "ghar mein paani", "ghar me paani", "ghar me pani", "andar aa gaya", "andar aa raha", "घर में पानी",
                  "घरात पाणी", "अंदर आ", "first floor", "ground floor flooded", "पानी अंदर", "पाणी आत"]),
]
RISING = ["rising", "increasing", "badh raha", "badh rha", "बढ़ रहा", "बढ़ता", "वाढत", "going up", "!!"]

RUMOUR_CLAIMS = [
    ("dam_burst", ["dam has burst", "dam burst", "dam broke", "dam toot", "dam tut", "baandh toot", "बांध टूट",
                   "बाँध टूट", "धरण फुटले", "धरण फुटलं", "lake burst", "powai lake burst", "vihar burst"]),
    ("camp_flooded", ["camp 3 is flooded", "camp 3 band", "camp 3 closed", "school camp flooded", "camp mein paani bhar",
                      "कैंप 3 बंद", "शिबिर बंद"]),
    ("power_cut_days", ["electricity cut for 3 days", "bijli 3 din", "power off for three days", "3 दिन बिजली"]),
    ("army_vip", ["boats only for vip", "army only for vip", "नेता के लिए नाव", "only rich people"]),
    ("whole_area_drown", ["whole kurla will drown", "pura kurla doob", "पूरा कुर्ला डूब", "10 feet water everywhere",
                          "tsunami"]),
]
REPOST_MARKERS = ["fwd", "forwarded", "please share", "pls share", "plz share", "share karo", "share kare", "share kara",
                  "aage bhejo", "आगे भेजें", "शेयर करें", "शेअर करा", "viral", "maximum share", "forward this"]
QUESTION_MARKERS = ["what should i do", "what do i do", "what to do", "what can i do", "kya karu", "kya karun",
                    "kya karein", "kya kare", "kya karna", "क्या करें", "क्या करूँ", "क्या करूं", "क्या करना",
                    "काय करू", "काय करावे", "काय करायचे", "how do i", "should i", "is it safe"]
FAQ_MARKERS = {
    "helplines": ["helpline", "number kya hai", "phone number of", "control room number", "हेल्पलाइन", "नंबर क्या"],
    "camps": ["camp kahan", "camp where", "where is the camp", "relief camp", "shelter", "kahan jayein",
              "शिविर कहाँ", "कैंप कहाँ", "शिबिर कुठे", "where can we stay", "camp open"],
    "family": ["is my family safe", "how to check", "family ka pata", "kaise pata", "परिवार सुरक्षित"],
}
SUPPLY_MARKERS = ["food", "khana", "khaana", "drinking water", "peene ka paani", "water bottle", "milk", "dudh", "doodh",
                  "ration", "medicine", "dawai", "davai", "blanket", "diapers", "baby food", "ors", "torch",
                  "खाना", "दूध", "दवाई", "राशन", "कंबल", "अन्न", "जेवण", "दूध पाहिजे", "औषध", "पिण्याचे पाणी",
                  "पीने का पानी", "पानी की बोतल", "paani ki bottle"]
ROAD_MARKERS = ["road blocked", "road band", "lane blocked", "rasta band", "raasta band", "road is closed",
                "road flooded", "water logged", "waterlogged", "पानी भरा", "रास्ता बंद", "रस्ता बंद", "road pe paani",
                "road par paani", "underpass", "subway flooded", "subway band", "tree fallen", "ped gir"]
POWER_MARKERS = ["power cut", "no electricity", "light gayi", "light nahi", "bijli nahi", "bijli gayi", "batti gul",
                 "बिजली नहीं", "बिजली गई", "लाइट नहीं", "वीज नाही", "लाईट गेली"]
SAFE_MARKERS = ["we are safe", "we are fine", "reached camp", "rescued us", "got rescued", "hum safe", "safe hain",
                "सुरक्षित हैं", "सुरक्षित आहोत", "bach gaye", "बच गए", "pahunch gaye camp"]
STATUS_MARKERS = ["any update", "kab aayega", "kab aayegi", "kab ayega", "still waiting", "no one came", "koi nahi aaya",
                  "कब आएगा", "कोई नहीं आया", "कधी येणार", "update?", "where is the boat", "boat kahan"]
WELFARE_MARKERS = ["not answering", "can't reach", "cannot reach", "phone off", "no contact", "not picking",
                   "phone nahi utha", "sampark nahi", "संपर्क नहीं", "फोन नहीं उठा", "फोन उचलत नाही", "check on",
                   "lives alone", "welfare check", "akele rehte"]
FIRST_PERSON = ["we ", "we're", "us ", "our ", "i am", "i'm", "my house", "hum ", "hamara", "hamare", "mera ghar",
                "हम ", "हमारे", "मैं", "मेरे", "आम्ही", "आमच्या", "माझ्या"]


def detect_language(text):
    t = text or ""
    if DEVANAGARI.search(t):
        mr = sum(1 for m in MARATHI_MARKERS if m in t)
        hi = sum(1 for m in HINDI_MARKERS if m in t)
        return "mr" if mr > hi else "hi"
    words = re.findall(r"[a-z']+", t.lower())
    joined = " " + " ".join(words) + " "
    hits = sum(1 for m in HINGLISH_MARKERS if f" {m} " in joined)
    return "hinglish" if hits >= 2 else "en"


def _has(t, words):
    return [w for w in words if w in t]


def _number_before(t, nouns):
    t = t.translate(geo.DEVANAGARI_DIGITS)
    m = re.search(r"(\d{1,2})\s*" + nouns, t)
    if m:
        return int(m.group(1))
    m = re.search(r"([^\s,.!?।]+)\s*" + nouns, t)
    if m and m.group(1) in NUM_WORDS:
        return NUM_WORDS[m.group(1)]
    m = re.search(r"(?:family of|we are|hum|हम|आम्ही)\s*(\d{1,2}|[a-zऀ-ॿ]+)\b", t)
    if m:
        v = m.group(1)
        if v.isdigit():
            return int(v)
        if v in NUM_WORDS:
            return NUM_WORDS[v]
    return None


def extract_people(t):
    n = _number_before(t, PEOPLE_NOUNS)
    if n:
        return n, False
    # A bare number as the whole reply to "how many people?" also counts.
    bare = t.strip().translate(geo.DEVANAGARI_DIGITS)
    m = re.fullmatch(r"(\d{1,2})\.?", bare)
    if m:
        return int(m.group(1)), False
    if bare in NUM_WORDS:
        return NUM_WORDS[bare], False
    return None, False


def extract_battery(t):
    m = re.search(r"(\d{1,3})\s*%", t.translate(geo.DEVANAGARI_DIGITS))
    if m and int(m.group(1)) <= 100:
        return int(m.group(1))
    return None


def extract_ages(t):
    ages = []
    for m in re.finditer(r"\b(\d{2})\s*(?:yrs?|years?|saal|साल|वर्ष|वर्षांच|y/o|yo)?\b", t.translate(geo.DEVANAGARI_DIGITS)):
        v = int(m.group(1))
        if 55 <= v <= 105:
            ages.append(v)
    return ages


def extract_name(text):
    """Find a name from the household registry, or a 'Name family' phrase."""
    t = text.lower()
    for h in scenario.households():
        for alias in h.get("aliases", []):
            if re.search(rf"(?<![\wऀ-ॿ]){re.escape(alias)}(?![a-z])", t):
                return h["name"], h["id"]
    m = re.search(r"\b(?!The\s|A\s)([A-Z][A-Za-z']{2,}(?:\s[A-Z][a-z]+)?)\s+(?:family|parivar|परिवार|कुटुंब)", text)
    if m:
        return f"{m.group(1)} family", None
    m = re.search(r"([ऀ-ॿ]{2,})\s+(?:परिवार|कुटुंब|परिवारा)", text)
    if m and m.group(1) not in ("एक", "मेरा", "मेरे", "हमारा", "आमचे", "माझे"):
        return f"{m.group(1)} family", None
    m = re.search(r"\b(?:my|meri|mere)\s+(?:mother|father|mom|dad|maa|papa|grandmother|uncle|aunt)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", text)
    if m:
        return m.group(1), None
    return None, None


def classify(t, fields):
    """Decide what kind of message this is."""
    if _has(t, SAFE_MARKERS):
        return "safe_report"
    for claim, words in RUMOUR_CLAIMS:
        if _has(t, words):
            fields["claim"] = claim
            return "rumour"
    is_question = bool(_has(t, QUESTION_MARKERS))
    for topic, words in FAQ_MARKERS.items():
        if _has(t, words):
            fields["faq"] = topic
            return "faq"
    if _has(t, STATUS_MARKERS) and not fields.get("water_level"):
        return "status_query"
    has_need = any([fields.get("water_level"), fields.get("vulnerable"), fields.get("medical"),
                    fields.get("people"), fields.get("danger")])
    if _has(t, WELFARE_MARKERS):
        return "welfare"
    if is_question and not fields.get("location_found"):
        return "question"
    if _has(t, SUPPLY_MARKERS) and not fields.get("water_level") in ("roof", "neck", "chest", "waist"):
        if not fields.get("medical") or fields.get("medical") == ["chronic"]:
            return "supplies"
    people_need = any([fields.get("vulnerable"), fields.get("medical"), fields.get("people"),
                       fields.get("danger"), fields.get("first_person")])
    if _has(t, ROAD_MARKERS) and not people_need:
        return "road_report"
    if _has(t, POWER_MARKERS) and not has_need:
        return "power_report"
    if has_need or _has(t, ["help", "bachao", "madad", "बचाओ", "मदद", "वाचवा", "rescue", "trapped", "phase", "phanse",
                             "फंसे", "अडकलो", "अडकले", "stuck"]):
        return "rescue"
    if is_question:
        return "question"
    return "other"


def extract(text):
    """Return a structured report from one message, using rules only."""
    t = (text or "").lower()
    lang = detect_language(text)
    fields = {"language": lang}

    people, implied = extract_people(t)
    vulnerable = sorted(k for k, words in VULNERABLE.items() if _has(t, words))
    ages = extract_ages(t)
    if ages and "elderly" not in vulnerable:
        vulnerable = sorted(vulnerable + ["elderly"])
    if "small child" in t or "baby" in t or "infant" in t or "बाळ" in t or "toddler" in t:
        fields["small_child"] = True
    medical = sorted(k for k, words in MEDICAL.items() if _has(t, words))
    danger = sorted(k for k, words in DANGER.items() if _has(t, words))
    water = next((level for level, words in WATER_LEVELS if _has(t, words)), None)
    if people is None and vulnerable:
        # "budhi amma aur bachcha" tells us at least two people.
        # A child is never alone, so a child alone still means two people.
        people, implied = max(len(vulnerable), 2 if "child" in vulnerable else 1), True

    geo_result = geo.geocode_landmark(text or "")
    name, household_id = extract_name(text or "")

    fields.update({
        "people": people,
        "people_implied": implied,
        "vulnerable": vulnerable,
        "ages": ages,
        "medical": medical,
        "danger": danger,
        "water_level": water,
        "rising": bool(_has(t, RISING)),
        "battery": extract_battery(t),
        "name": name,
        "household_hint": household_id,
        "location_found": geo_result["found"],
        "location_text": geo_result.get("why") if geo_result["found"] else None,
        "lane": geo_result.get("lane"),
        "landmark": geo_result.get("landmark"),
        "lat": geo_result.get("lat"),
        "lng": geo_result.get("lng"),
        "node": geo_result.get("node"),
        "geo_confidence": geo_result.get("confidence", 0.0),
        "repost": bool(_has(t, REPOST_MARKERS)),
        "first_person": bool(_has(" " + t + " ", FIRST_PERSON)),
        "road": _road_mentioned(text) if _has(t, ROAD_MARKERS) else None,
    })
    fields["household_guess"] = None if household_id else guess_household(fields)
    fields["intent"] = classify(t, fields)
    return fields


def guess_household(fields):
    """Household memory: if a report without a name comes from a registered household's
    landmark and describes the same kind of people, note it as a likely match."""
    if not fields.get("landmark") or not fields.get("vulnerable"):
        return None
    matches = []
    for h in scenario.households():
        if h.get("landmark") != fields["landmark"] or h.get("status") == "safe":
            continue
        kinds = set()
        for m in h["members"]:
            note = (m.get("note") or "") + (" elderly" if m.get("age", 0) >= 60 else "") + (" child" if m.get("age", 99) <= 14 else "")
            kinds |= {k for k in ("elderly", "child") if k in note}
        if set(fields["vulnerable"]) <= kinds:
            matches.append(h["id"])
    return matches[0] if len(matches) == 1 else None


def _road_mentioned(text):
    lane = geo.parse_lane(text)
    if lane:
        return f"Lane {lane}"
    t = text.lower()
    for name in ("station road", "market road", "river road", "school lane", "sector 3 road", "hall road"):
        if name in t:
            return name.title()
    return None


def similarity(a, b):
    """Cheap text similarity used when embeddings are not available."""
    return fuzz.token_set_ratio(a or "", b or "") / 100
