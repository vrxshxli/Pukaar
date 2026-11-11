"""Generate a deterministic flood night of about 300 messages, with ground truth.

Usage: python scripts/generate_flood_night.py
Writes data/scenario/flood_night.json. The same seed always gives the same night.

Every message carries hidden ground truth: which family it is about, what kind
of message it is, the true priority, whether it is a rumour, and which fields
it actually states. The evaluator compares Pukaar against this.
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 2026
OUT = Path(__file__).resolve().parents[1] / "data" / "scenario" / "flood_night.json"
START = datetime(2026, 7, 14, 21, 30)
END = datetime(2026, 7, 15, 2, 30)

rng = random.Random(SEED)
messages = []
phone_counter = [10000]

SURNAMES = ["Patil", "Kadam", "Khan", "Bhatt", "Sayyed", "Lobo", "Menon", "Wagh", "Kharat", "Dalvi", "Shirke",
            "Chougule", "Barve", "Paradkar", "Ingle", "Tambe", "Kotian", "Shaikh Noor", "Pereira", "Gaonkar", "D'Souza", "Shinde", "More", "Ansari", "Pawar", "Jadhav",
            "Sawant", "Mishra", "Iyer", "Fernandes", "Qureshi", "Bhosle", "Gaikwad", "Tiwari", "Chavan", "Naik",
            "Salvi", "Pandey", "Mhatre", "Rane", "Desai", "Kamble", "Lokhande", "Siddiqui", "Pillai", "Mane",
            "Dubey", "Thakur", "Gawde", "Shetty", "Rathod", "Waghmare", "Parab", "Malik", "Joshi", "Sheikh Ali",
            "Kulkarni", "Bansode", "Hegde", "Nair", "Raut", "Solanki", "Mistry", "Kale", "Sutar", "Ghosh", "Rao"]
SURNAMES_HI = {"Patil": "पाटिल", "Kadam": "कदम", "Gupta": "गुप्ता", "Yadav": "यादव", "Khan": "खान", "Shinde": "शिंदे",
               "More": "मोरे", "Ansari": "अंसारी", "Pawar": "पवार", "Jadhav": "जाधव", "Sawant": "सावंत", "Mishra": "मिश्रा",
               "Qureshi": "कुरैशी", "Tiwari": "तिवारी", "Chavan": "चव्हाण", "Pandey": "पांडे", "Kamble": "कांबळे",
               "Dubey": "दुबे", "Thakur": "ठाकुर", "Joshi": "जोशी", "Mane": "माने", "Raut": "राऊत", "Kale": "काळे"}
LANDMARK_ON_LANE = {4: "hanuman_temple", 7: "lane7_mosque", 8: "water_tank"}

LOC = {
    "en": lambda lane, lm: {None: f"Lane {lane}", "hanuman_temple": f"behind Hanuman temple, Lane {lane}",
                            "lane7_mosque": f"near the mosque on Lane {lane}", "water_tank": f"near the water tank, Lane {lane}"}[lm],
    "hi": lambda lane, lm: {None: f"गली {lane}", "hanuman_temple": f"गली {lane}, हनुमान मंदिर के पीछे",
                            "lane7_mosque": f"गली {lane} मस्जिद के पास", "water_tank": f"गली {lane}, पानी की टंकी के पास"}[lm],
    "mr": lambda lane, lm: {None: f"गल्ली {lane}", "hanuman_temple": f"गल्ली {lane}, हनुमान मंदिराच्या मागे",
                            "lane7_mosque": f"गल्ली {lane} मशिदीजवळ", "water_tank": f"गल्ली {lane}, पाण्याची टाकीजवळ"}[lm],
    "hinglish": lambda lane, lm: {None: f"gali {lane}", "hanuman_temple": f"gali {lane} mandir ke peeche",
                                  "lane7_mosque": f"gali {lane} masjid ke paas", "water_tank": f"gali {lane} tanki ke paas"}[lm],
}
WATER = {
    "en": {"knee": "water is at knee level", "waist": "water is at waist level", "chest": "water is chest deep",
           "roof": "we are on the roof", "entering": "water is entering the house"},
    "hi": {"knee": "पानी घुटनों तक आ गया है", "waist": "पानी कमर तक है", "chest": "पानी छाती तक है",
           "roof": "हम छत पर हैं", "entering": "घर में पानी आ गया है"},
    "mr": {"knee": "पाणी गुडघ्यापर्यंत आले आहे", "waist": "पाणी कंबरेपर्यंत आहे", "chest": "पाणी छातीपर्यंत आहे",
           "roof": "आम्ही छतावर आहोत", "entering": "घरात पाणी आले आहे"},
    "hinglish": {"knee": "paani ghutno tak aa gaya hai", "waist": "paani kamar tak hai", "chest": "paani chhati tak hai",
                 "roof": "hum chhat par hain", "entering": "ghar mein paani aa gaya hai"},
}
VULN = {
    "en": {"elderly": "my old grandmother", "child": "a small child", "pregnant": "a pregnant woman", "disabled": "my father in a wheelchair"},
    "hi": {"elderly": "बुज़ुर्ग दादी", "child": "छोटा बच्चा", "pregnant": "गर्भवती बहू", "disabled": "विकलांग पिताजी"},
    "mr": {"elderly": "आजी", "child": "लहान बाळ", "pregnant": "गरोदर सून", "disabled": "अपंग वडील"},
    "hinglish": {"elderly": "budhi dadi", "child": "chhota bachcha", "pregnant": "pregnant bahu", "disabled": "viklang papa"},
}
MED = {
    "en": {"fever": "the child has fever", "injured": "someone is injured and bleeding", "dialysis": "grandfather needs dialysis",
           "unconscious": "grandmother has fainted and is unconscious", "breathing": "father can't breathe properly"},
    "hi": {"fever": "बच्चे को बुखार है", "injured": "एक आदमी घायल है", "dialysis": "दादाजी को डायलिसिस चाहिए",
           "unconscious": "दादी बेहोश हो गई हैं", "breathing": "पिताजी को सांस लेने में तकलीफ है"},
    "mr": {"fever": "बाळाला ताप आहे", "injured": "एक जण जखमी आहे", "dialysis": "आजोबांना डायलिसिस हवे आहे",
           "unconscious": "आजी बेशुद्ध झाल्या आहेत", "breathing": "वडिलांना श्वास घ्यायला त्रास होत आहे"},
    "hinglish": {"fever": "bachche ko bukhar hai", "injured": "ek aadmi ghayal hai", "dialysis": "dadaji ko dialysis chahiye",
                 "unconscious": "dadi behosh ho gayi hain", "breathing": "papa ko saans lene mein dikkat hai"},
}
THEY_ON_ROOF = {"en": "they are on the roof", "hi": "वे छत पर हैं", "mr": "ते छतावर आहेत", "hinglish": "woh chhat par hain"}
AND = {"en": " and ", "hi": " और ", "mr": " आणि ", "hinglish": " aur "}


def new_phone():
    phone_counter[0] += 1
    return f"+91 90000 {phone_counter[0]}"


def at(hhmm_or_dt):
    if isinstance(hhmm_or_dt, datetime):
        return hhmm_or_dt
    h, m = (int(x) for x in hhmm_or_dt.split(":")[:2])
    t = START.replace(hour=h, minute=m)
    return t + timedelta(days=1) if h < 12 else t


def add(time, phone, text, channel, language, kind, family=None, priority=None, fields=None, name=None, rumour=False):
    messages.append({
        "time": at(time).isoformat(),
        "phone": phone, "sender": name, "channel": channel, "language": language, "text": text,
        "truth": {"family": family, "kind": kind, "priority": priority, "rumour": rumour, "fields": fields or {}},
    })


def truth_priority(f):
    """The designer's rubric for the true priority, written separately from Triage's rules."""
    water, vuln, med = f.get("water"), set(f.get("vulnerable", [])), set(f.get("medical", []))
    if water in ("roof", "chest") or med & {"unconscious", "breathing", "injured", "dialysis"} or f.get("danger"):
        return "P1"
    if vuln and water in ("knee", "waist") and (med or len(vuln) >= 2):
        return "P1"
    if vuln or water in ("waist", "entering"):
        return "P2"
    return "P3"


# The five named households from the scenario.

def named_households():
    kamla = "kamla"
    k_fields = {"people": 3, "vulnerable": ["child", "elderly"], "medical": ["fever"], "water": "knee", "lane": "Lane 4"}
    add("21:38", "+91 90000 00412", "पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे",
        "voice", "hi", "rescue", kamla, "P1",
        {"people": None, "vulnerable": ["child"], "medical": ["fever"], "water": "knee", "lane": "Lane 4"}, "Kamla Devi")
    add("21:39", "+91 90000 00412", "3 लोग। पोते को बुखार है", "voice", "hi", "followup", kamla, "P1",
        {"people": 3, "vulnerable": ["child"], "medical": ["fever"], "water": None, "lane": None}, "Kamla Devi")
    add("21:41", "+91 90000 05101", "Please help my mother Kamla Devi, Lane 4 behind Hanuman temple, Shanti Nagar. Water rising!!",
        "post", "en", "rescue", kamla, "P1",
        {"people": None, "vulnerable": [], "medical": [], "water": None, "lane": "Lane 4"}, "Priya (daughter)")
    add("21:44", "+91 90000 05102", "shantinagar gali 4 mandir ke peeche budhi amma aur bachcha phase hai",
        "sms", "hinglish", "rescue", kamla, "P1",
        {"people": None, "vulnerable": ["child", "elderly"], "medical": [], "water": None, "lane": "Lane 4"}, "Neighbour")
    add("22:05", new_phone(), "Kamla Devi aur unka pota gali 4 mein abhi bhi phase hain, please share karo, phone 14% hai",
        "forward", "hinglish", "rescue", kamla, "P1",
        {"people": None, "vulnerable": ["child"], "medical": [], "water": None, "lane": "Lane 4"})

    jos = "joseph"
    add("21:52", "+91 90000 00909", "We are 5 people on the roof at Lane 9, small child with us, please hurry. Joseph family",
        "sms", "en", "rescue", jos, "P1",
        {"people": 5, "vulnerable": ["child"], "medical": [], "water": "roof", "lane": "Lane 9"}, "Thomas Joseph")
    add("21:58", new_phone(), "Joseph family lane 9 chhat par phase hain, 5 log, chhota bachcha bhi hai",
        "sms", "hinglish", "rescue", jos, "P1",
        {"people": 5, "vulnerable": ["child"], "medical": [], "water": "roof", "lane": "Lane 9"})
    add("22:15", new_phone(), "URGENT: Joseph family of 5 stuck on the roof in Lane 9 Shanti Nagar with a toddler and grandma 72",
        "post", "en", "rescue", jos, "P1",
        {"people": 5, "vulnerable": ["child", "elderly"], "medical": [], "water": "roof", "lane": "Lane 9"})

    sh = "shaikh"
    add("22:02", "+91 90000 00707", "गली 7 मस्जिद के पास पहली मंजिल पर पानी अंदर आ रहा है, 4 लोग हैं",
        "voice", "hi", "rescue", sh, "P1",
        {"people": 4, "vulnerable": [], "medical": [], "water": "entering", "lane": "Lane 7"}, "Rukhsar Shaikh")
    add("22:20", "+91 90000 00707", "गली 7 मस्जिद के पास गैस की बदबू आ रही है और पानी अंदर है, क्या करें?",
        "voice", "hi", "rescue", sh, "P1",
        {"people": None, "vulnerable": [], "medical": [], "water": "entering", "lane": "Lane 7", "danger": ["gas"]}, "Rukhsar Shaikh")
    add("22:31", new_phone(), "Shaikh family gali no 7 masjid ke paas, ghar mein paani aa gaya hai aur gas leak bhi hai",
        "sms", "hinglish", "rescue", sh, "P1",
        {"people": None, "vulnerable": [], "medical": [], "water": "entering", "lane": "Lane 7", "danger": ["gas"]})

    for t, text, lang, ch in [
        ("21:47", "FWD: Pinto family Lane 2 trapped with grandma, 4 people, please share!!", "en", "forward"),
        ("22:24", "Pinto family gali 2 mein phase hain, budhi dadi ke saath, please share karo", "hinglish", "forward"),
        ("22:58", "पिंटो परिवार गली 2 में फंसा है, दादी के साथ, कृपया शेयर करें", "hi", "forward"),
        ("23:40", "Pls share: Pinto family Lane 2 Shanti Nagar, 4 people incl. 78 yr old grandmother, water rising", "en", "post"),
        ("00:35", "पिंटो कुटुंब गल्ली 2 मध्ये अडकले आहे, आजी सोबत आहेत, कृपया शेअर करा", "mr", "forward"),
        ("01:20", "Still no help for Pinto family lane 2?? forward this", "en", "forward"),
    ]:
        add(t, new_phone(), text, ch, lang, "repost_safe", "pinto", None,
            {"people": None, "vulnerable": ["elderly"], "medical": [], "water": None, "lane": "Lane 2"})

    add("22:40", "+91 90000 05300", "माझे वडील मोहन सेक्टर 3 मध्ये एकटे राहतात, फोन उचलत नाही. कृपया कोणी तरी बघा",
        "sms", "mr", "welfare", "mohan", "P2",
        {"people": None, "vulnerable": ["elderly"], "medical": [], "water": None, "lane": "Sector 3"}, "Mohan's daughter")
    add("23:05", new_phone(), "Mohan kaka sector 3 akele rehte hain, phone nahi utha rahe, check on him please",
        "sms", "hinglish", "welfare", "mohan", "P2",
        {"people": None, "vulnerable": ["elderly"], "medical": [], "water": None, "lane": "Sector 3"})


# Generated families with duplicate reports from different people.

def make_family(i, surname, lane, landmark):
    vulnerable = sorted(set(rng.choices(["elderly", "child", "pregnant", "disabled"], weights=[5, 5, 1, 1], k=rng.choice([0, 0, 1, 1, 2]))))
    medical = []
    if rng.random() < 0.22:
        medical = [rng.choice(["fever", "fever", "injured", "dialysis", "unconscious", "breathing"])]
        if medical == ["fever"] and "child" not in vulnerable:
            vulnerable = sorted(set(vulnerable) | {"child"})
    water = rng.choices(["knee", "waist", "chest", "roof", "entering"], weights=[4, 4, 1, 2, 3])[0]
    people = max(rng.randint(1, 7), len(vulnerable) + 1 if vulnerable else 1)
    f = {"id": f"fam{i:02d}", "surname": surname, "lane": lane, "landmark": landmark, "people": people,
         "vulnerable": vulnerable, "medical": medical, "water": water}
    f["priority"] = truth_priority(f)
    return f


def render(f, lang, role, include):
    """One report about a family. `include` says which facts this reporter mentions."""
    loc = LOC[lang](f["lane"], f["landmark"] if include.get("landmark") else None)
    water = WATER[lang][f["water"]] if include.get("water") else None
    if water and f["water"] == "roof" and role != "self":
        water = THEY_ON_ROOF[lang]
    vuln = [VULN[lang][v] for v in f["vulnerable"]] if include.get("vulnerable") else []
    med = [MED[lang][m] for m in f["medical"]] if include.get("medical") else []
    n = f["people"] if include.get("people") else None
    sur = f["surname"] if lang in ("en", "hinglish") else SURNAMES_HI.get(f["surname"], f["surname"])
    name = sur if include.get("name") else None
    parts = []
    if lang == "en":
        if role == "self":
            parts.append(f"Help! {water or 'we are stuck'} at {loc}.")
            if n:
                parts.append(f"We are {n} people.")
        else:
            who = f"The {name} family" if name else "A family"
            parts.append(f"{who} is stuck at {loc}" + (f", {water}" if water else "") + ".")
            if n:
                parts.append(f"{n} people inside.")
        if vuln:
            parts.append("With " + " and ".join(vuln) + ".")
        parts += [m.capitalize() + "." for m in med]
    elif lang == "hi":
        if role == "self":
            parts.append(f"{loc} में {water or 'हम फंसे हैं'}।")
            if n:
                parts.append(f"हम {n} लोग हैं।")
            parts.append("जल्दी मदद भेजिए")
        else:
            who = f"{name} परिवार" if name else "एक परिवार"
            parts.append(f"{who} {loc} में फंसा है" + (f", {water}" if water else "") + "।")
            if n:
                parts.append(f"{n} लोग हैं।")
        if vuln:
            parts.append(AND["hi"].join(vuln) + " साथ में हैं।")
        parts += [m + "।" for m in med]
    elif lang == "mr":
        if role == "self":
            parts.append(f"{loc} मध्ये {water or 'आम्ही अडकलो आहोत'}.")
            if n:
                parts.append(f"आम्ही {n} जण आहोत.")
            parts.append("लवकर मदत करा")
        else:
            who = f"{name} कुटुंब" if name else "एक कुटुंब"
            parts.append(f"{who} {loc} मध्ये अडकले आहे" + (f", {water}" if water else "") + ".")
            if n:
                parts.append(f"{n} जण आहेत.")
        if vuln:
            parts.append(AND["mr"].join(vuln) + " सोबत आहेत.")
        parts += [m + "." for m in med]
    else:
        if role == "self":
            parts.append(f"{loc} mein {water or 'hum phase hain'},")
            if n:
                parts.append(f"hum {n} log hain,")
            parts.append("jaldi madad bhejo")
        else:
            who = f"{name} family" if name else "ek family"
            parts.append(f"{who} {loc} mein phasi hai" + (f", {water}" if water else ""))
            if n:
                parts.append(f"{n} log hain")
        if vuln:
            parts.append("saath mein " + AND["hinglish"].join(vuln))
        parts += med
    text = " ".join(parts)
    fields = {"people": n, "vulnerable": f["vulnerable"] if include.get("vulnerable") else [],
              "medical": f["medical"] if include.get("medical") else [],
              "water": f["water"] if include.get("water") else None, "lane": f"Lane {f['lane']}"}
    return text, fields


def generated_families(count=66):
    families = []
    surnames = rng.sample(SURNAMES, count)
    for i, surname in enumerate(surnames):
        lane = rng.choice([1, 2, 3, 3, 4, 5, 5, 6, 6, 7, 8, 8, 9])
        landmark = LANDMARK_ON_LANE.get(lane) if rng.random() < 0.5 else None
        families.append(make_family(i, surname, lane, landmark))

    # Two different families sharing a lane and landmark, to test that we don't over-merge.
    families.append(make_family(90, "Gupta", 4, "hanuman_temple"))
    families[-1]["id"] = "fam90"
    families.append(make_family(91, "Yadav", 4, "hanuman_temple"))
    families[-1]["id"] = "fam91"

    for f in families:
        first = START + timedelta(minutes=rng.randint(10, 250))
        n_reports = rng.choices([1, 2, 3, 4], weights=[2, 4, 3, 2])[0]
        langs = rng.sample(["hi", "mr", "hinglish", "en"], k=min(n_reports, 4)) + ["hinglish"] * max(0, n_reports - 4)
        self_phone = new_phone()
        for r in range(n_reports):
            role = "self" if r == 0 else rng.choice(["relative", "neighbour"])
            include = {"water": rng.random() < 0.85, "vulnerable": rng.random() < 0.8, "medical": rng.random() < 0.9,
                       "people": role == "self" or rng.random() < 0.5, "landmark": f["landmark"] is not None and rng.random() < 0.8,
                       "name": role != "self" or rng.random() < 0.3}
            # Some first messages forget the location and get a follow-up question.
            missing_location = role == "self" and rng.random() < 0.12
            text, fields = render(f, langs[r], role, include)
            when = first + timedelta(minutes=0 if r == 0 else rng.randint(2, 35) * r)
            phone = self_phone if role == "self" else new_phone()
            kind = "rescue"
            if missing_location:
                text = strip_location(text, langs[r], f)
                fields = {**fields, "lane": None}
            add(when, phone, text, rng.choice(["voice", "sms", "chat"]) if role == "self" else rng.choice(["sms", "post", "forward", "call"]),
                langs[r], kind, f["id"], f["priority"], fields)
            if missing_location:
                answer = {"en": f"Lane {f['lane']}", "hi": f"गली {f['lane']}", "mr": f"गल्ली {f['lane']}",
                          "hinglish": f"gali {f['lane']}"}[langs[r]]
                add(when + timedelta(minutes=2), phone, answer, "chat", langs[r], "followup", f["id"], f["priority"],
                    {"people": None, "vulnerable": [], "medical": [], "water": None, "lane": f"Lane {f['lane']}"})
        f["self_phone"] = self_phone
        f["first"] = first
    return families


def strip_location(text, lang, f):
    for loc in (LOC[lang](f["lane"], f["landmark"]), LOC[lang](f["lane"], None)):
        text = text.replace(f" at {loc}", "").replace(f"{loc} में ", "").replace(f"{loc} मध्ये ", "") \
            .replace(f"{loc} mein ", "").replace(loc, "")
    return text.strip()


def status_and_safe(families):
    for f in rng.sample(families, 18):
        t = f["first"] + timedelta(minutes=rng.randint(25, 60))
        text = rng.choice(["any update? still waiting", "boat kab aayegi? koi nahi aaya", "कोई नहीं आया अभी तक, कब आएगा?",
                           "अजून कोणी आले नाही, कधी येणार?"])
        lang = "en" if text.startswith("any") else "hinglish" if text.startswith("boat") else "hi" if "कोई" in text else "mr"
        add(t, f["self_phone"], text, "chat", lang, "status", f["id"], None, {})
    for f in rng.sample(families, 5):
        t = f["first"] + timedelta(minutes=rng.randint(70, 120))
        text = rng.choice(["we are safe now, reached camp", "hum safe hain, camp pahunch gaye", "हम सुरक्षित हैं, धन्यवाद"])
        lang = "en" if text.startswith("we") else "hinglish" if text.startswith("hum") else "hi"
        add(t, f["self_phone"], text, "chat", lang, "safe", f["id"], None, {})


RUMOURS = [
    ("Powai dam has burst!! whole Kurla will drown, forward to all", "en", "dam_burst"),
    ("Vihar lake ka dam toot gaya, sab log upar jao, share karo", "hinglish", "dam_burst"),
    ("बांध टूट गया है, पूरा कुर्ला डूब जाएगा, सबको बताओ", "hi", "dam_burst"),
    ("पवई धरण फुटले आहे, सगळ्यांनी वर जा", "mr", "dam_burst"),
    ("Breaking: dam burst near Powai, 10 feet water everywhere in 1 hour", "en", "dam_burst"),
    ("Dam burst news is true, my cousin in BMC said so, forward", "en", "dam_burst"),
    ("Camp 3 is flooded, don't go there, forward", "en", "camp_flooded"),
    ("camp 3 band ho gaya, wahan paani bhar gaya", "hinglish", "camp_flooded"),
    ("कैंप 3 बंद हो गया है, वहाँ मत जाओ", "hi", "camp_flooded"),
    ("Electricity cut for 3 days in all of Kurla, charge your phones", "en", "power_cut_days"),
    ("bijli 3 din tak nahi aayegi, sab charge kar lo", "hinglish", "power_cut_days"),
    ("3 दिन बिजली नहीं आएगी, सबको बताओ", "hi", "power_cut_days"),
    ("Army boats only for VIP colonies, nobody will come for us", "en", "army_vip"),
    ("boats only for vip, hum logon ke liye koi nahi aayega", "hinglish", "army_vip"),
    ("Tsunami warning for Mumbai tonight, move to higher floors", "en", "whole_area_drown"),
]

QUESTIONS = [
    ("Water is entering the house, what should I do?", "en", "question"),
    ("paani badh raha hai, kya karein?", "hinglish", "question"),
    ("घर में पानी आ रहा है, क्या करें?", "hi", "question"),
    ("घरात पाणी येत आहे, काय करू?", "mr", "question"),
    ("बिजली का तार पानी में गिरा है, क्या करें?", "hi", "question"),
    ("There is a spark near the meter box and water on the floor, what should I do?", "en", "question"),
    ("gas ki smell aa rahi hai kitchen mein, kya karu?", "hinglish", "question"),
    ("Where is the nearest relief camp?", "en", "faq"),
    ("relief camp kahan hai? kahan jayein?", "hinglish", "faq"),
    ("शिविर कहाँ है? हम कहाँ जाएँ?", "hi", "faq"),
    ("शिबिर कुठे आहे?", "mr", "faq"),
    ("What is the helpline number for the control room?", "en", "faq"),
    ("हेल्पलाइन नंबर क्या है?", "hi", "faq"),
    ("How do I check if my family is safe?", "en", "faq"),
    ("Is it safe to walk to Station Road now?", "en", "question"),
]

FIELD_REPORTS = [
    ("Lane 6 road blocked, water above waist near the market", "en", "road", "Lane 6"),
    ("Station Road pe paani bhar gaya, rasta band hai", "hinglish", "road", "Station Road"),
    ("River Road flooded, two cars stuck, road is closed", "en", "road", "River Road"),
    ("गली 6 में पानी भरा है, रास्ता बंद है", "hi", "road", "Lane 6"),
    ("Lane 3 waterlogged, tree fallen near the corner", "en", "road", "Lane 3"),
    ("market road pe paani, raasta band", "hinglish", "road", "Market Road"),
    ("गल्ली 5 मध्ये रस्ता बंद आहे, पाणी भरले", "mr", "road", "Lane 5"),
    ("Lane 6 still blocked, water rising near the shops", "en", "road", "Lane 6"),
    ("light gayi lane 3 mein, sab andhera hai", "hinglish", "power", None),
    ("No electricity in Lane 8 since 10 pm", "en", "power", None),
    ("गली 2 में बिजली नहीं है", "hi", "power", None),
    ("power cut in whole Shanti Nagar", "en", "power", None),
    ("लाईट गेली आहे गल्ली 9 मध्ये", "mr", "power", None),
]

SUPPLIES = [
    ("Need drinking water and food for 30 people at Camp 5 community hall", "en", "sup_camp5"),
    ("Camp 5 mein khana aur peene ka paani chahiye, 30 log hain", "hinglish", "sup_camp5"),
    ("Lane 3 mein 10 logon ke liye khana chahiye", "hinglish", "sup_lane3"),
    ("गली 3 में खाना और दूध चाहिए, 10 लोग हैं", "hi", "sup_lane3"),
    ("Baby food and milk needed near the mosque on lane 7", "en", "sup_mosque"),
    ("मशिदीजवळ गल्ली 7 मध्ये दूध आणि औषध पाहिजे", "mr", "sup_mosque"),
    ("Need blankets and ORS at Camp 3 school, many children", "en", "sup_camp3"),
    ("camp 3 school mein blanket aur ORS chahiye", "hinglish", "sup_camp3"),
    ("Lane 8 near the water tank, need drinking water bottles for 15 people", "en", "sup_tank"),
    ("गली 8 टंकी के पास पीने का पानी चाहिए, 15 लोग", "hi", "sup_tank"),
    ("Diabetic patient needs insulin, Lane 1, house 22", "en", "sup_lane1"),
    ("Lane 9 roof pe log hain, unko khana chahiye", "hinglish", "sup_lane9"),
]


def scattered(items, kind_fn):
    for item in items:
        when = START + timedelta(minutes=rng.randint(5, 290))
        kind_fn(when, item)


def background():
    def rumour(when, item):
        text, lang, claim = item
        add(when, new_phone(), text, "forward", lang, "rumour", f"rumour_{claim}", None, {"claim": claim}, rumour=True)
    scattered(RUMOURS, rumour)

    def question(when, item):
        text, lang, kind = item
        add(when, new_phone(), text, "chat", lang, kind, None, None, {})
    scattered(QUESTIONS * 2, question)

    def field(when, item):
        text, lang, kind, road = item
        if road == "Lane 6" and when < at("23:00"):
            when = at("23:00") + timedelta(minutes=rng.randint(5, 60))
        add(when, new_phone(), text, rng.choice(["sms", "chat", "call"]), lang, kind, None, None, {"road": road})
    scattered(FIELD_REPORTS * 2, field)

    def supply(when, item):
        text, lang, group = item
        add(when, new_phone(), text, "sms", lang, "supplies", group, "P3", {})
    scattered(SUPPLIES * 2, supply)


def main():
    named_households()
    families = generated_families()
    status_and_safe(families)
    background()
    messages.sort(key=lambda m: m["time"])
    events = [{"time": at("23:10").isoformat(), "type": "volunteer", "team": "boat2", "action": "blocked", "road": "Lane 6",
               "note": "Lane 6 floods during the night"}]
    families_out = {f["id"]: {k: f[k] for k in ("surname", "lane", "landmark", "people", "vulnerable", "medical", "water", "priority")}
                    for f in families}
    families_out.update({
        "kamla": {"surname": "Kamla Devi", "lane": 4, "priority": "P1"},
        "joseph": {"surname": "Joseph", "lane": 9, "priority": "P1"},
        "shaikh": {"surname": "Shaikh", "lane": 7, "priority": "P1"},
        "pinto": {"surname": "Pinto", "lane": 2, "priority": None, "already_safe": True},
        "mohan": {"surname": "Mohan", "lane": "Sector 3", "priority": "P2"},
    })
    for i, m in enumerate(messages, 1):
        m["id"] = i
    OUT.write_text(json.dumps({"seed": SEED, "start": START.isoformat(), "end": END.isoformat(),
                               "messages": messages, "events": events, "families": families_out},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = {}
    for m in messages:
        kinds[m["truth"]["kind"]] = kinds.get(m["truth"]["kind"], 0) + 1
    langs = {}
    for m in messages:
        langs[m["language"]] = langs.get(m["language"], 0) + 1
    print(f"Wrote {len(messages)} messages to {OUT}")
    print("By kind:", dict(sorted(kinds.items())))
    print("By language:", dict(sorted(langs.items())))


if __name__ == "__main__":
    main()
