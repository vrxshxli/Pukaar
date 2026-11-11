"""Reply templates in English, Hindi, Marathi and Hinglish (romanised Hindi).

The Hindi and Marathi lines should be checked by a native speaker before any
real use.
"""

TEMPLATES = {
    "ack_new": {
        "en": "Your message has reached the Pukaar control room. Ticket {ticket} is open.",
        "hi": "आपका संदेश मिल गया है। टिकट {ticket} खुला है।",
        "mr": "तुमचा संदेश मिळाला आहे. तिकीट {ticket} उघडले आहे.",
        "hinglish": "Aapka message mil gaya hai. Ticket {ticket} khul gaya hai.",
    },
    "ask_people": {
        "en": "How many people are with you?",
        "hi": "घर में कितने लोग हैं?",
        "mr": "घरात किती लोक आहेत?",
        "hinglish": "Aapke saath kitne log hain?",
    },
    "ask_location": {
        "en": "Where are you? Please send your lane number and a nearby landmark (temple, mosque, water tank).",
        "hi": "आप कहाँ हैं? कृपया अपनी गली का नंबर और पास की कोई पहचान (मंदिर, मस्जिद, पानी की टंकी) बताइए।",
        "mr": "तुम्ही कुठे आहात? कृपया तुमच्या गल्लीचा नंबर आणि जवळची खूण (मंदिर, मशीद, पाण्याची टाकी) सांगा.",
        "hinglish": "Aap kahan ho? Apni gali ka number aur paas ki koi pehchaan (mandir, masjid, paani ki tanki) bataiye.",
    },
    "linked": {
        "en": "{count} reports about this family are now linked to ticket {ticket}. You will all get the same updates.",
        "hi": "इस परिवार के बारे में {count} संदेश अब टिकट {ticket} से जुड़ गए हैं। सबको एक जैसी जानकारी मिलेगी।",
        "mr": "या कुटुंबाबद्दलचे {count} संदेश आता तिकीट {ticket} शी जोडले आहेत. सर्वांना सारखीच माहिती मिळेल.",
        "hinglish": "Is family ke baare mein {count} messages ab ticket {ticket} se jud gaye hain. Sabko same update milega.",
    },
    "team_coming": {
        "en": "{team} is on the way to {title}, about {eta} minutes. Keep your phone on and stay on the highest floor.",
        "hi": "{team} आपकी ओर आ रही है, लगभग {eta} मिनट। फ़ोन चालू रखें, ऊँची जगह पर रहें।",
        "mr": "{team} तुमच्याकडे येत आहे, सुमारे {eta} मिनिटे. फोन चालू ठेवा, उंच जागी राहा.",
        "hinglish": "{team} aapki taraf aa rahi hai, lagbhag {eta} minute. Phone chalu rakhiye, oonchi jagah par rahiye.",
    },
    "otp": {
        "en": "When the team reaches you, tell them this code: {otp}",
        "hi": "टीम पहुँचने पर यह OTP बताएँ: {otp}",
        "mr": "टीम पोहोचल्यावर हा OTP सांगा: {otp}",
        "hinglish": "Team pahunchne par yeh OTP bataiye: {otp}",
    },
    "rerouted": {
        "en": "{team} has taken a different route because {road} is flooded. New time: about {eta} minutes.",
        "hi": "{road} में पानी भरा है, इसलिए {team} दूसरे रास्ते से आ रही है। नया समय: लगभग {eta} मिनट।",
        "mr": "{road} मध्ये पाणी भरले आहे, म्हणून {team} दुसऱ्या मार्गाने येत आहे. नवीन वेळ: सुमारे {eta} मिनिटे.",
        "hinglish": "{road} mein paani bhara hai, isliye {team} doosre raaste se aa rahi hai. Naya time: lagbhag {eta} minute.",
    },
    "safe": {
        "en": "{title} was rescued at {time} and is now safe at {camp}.",
        "hi": "{title} को {time} बजे बचा लिया गया है और अब {camp} में सुरक्षित हैं।",
        "mr": "{title} यांची {time} वाजता सुटका झाली असून ते आता {camp} येथे सुरक्षित आहेत.",
        "hinglish": "{title} ko {time} baje bacha liya gaya hai, ab {camp} mein safe hain.",
    },
    "confirm_safe": {
        "en": "Please reply 1 to confirm your family is safe, so we can close ticket {ticket}.",
        "hi": "कृपया 1 लिखकर पुष्टि करें कि आपका परिवार सुरक्षित है, ताकि टिकट {ticket} बंद हो सके।",
        "mr": "तुमचे कुटुंब सुरक्षित आहे याची खात्री करण्यासाठी कृपया 1 लिहा, म्हणजे तिकीट {ticket} बंद करता येईल.",
        "hinglish": "Family safe hai to 1 likh kar confirm kijiye, taaki ticket {ticket} band ho sake.",
    },
    "closed": {
        "en": "Thank you. Ticket {ticket} is closed. Stay safe.",
        "hi": "धन्यवाद। टिकट {ticket} बंद कर दिया गया है। सुरक्षित रहें।",
        "mr": "धन्यवाद. तिकीट {ticket} बंद केले आहे. सुरक्षित राहा.",
        "hinglish": "Dhanyavaad. Ticket {ticket} band kar diya gaya hai. Safe rahiye.",
    },
    "already_safe": {
        "en": "Good news: {title} was rescued at {time} and is safe at {camp}. Please don't forward the old request any more.",
        "hi": "अच्छी खबर: {title} को {time} बजे बचा लिया गया था और वे {camp} में सुरक्षित हैं। कृपया पुराना संदेश आगे न भेजें।",
        "mr": "चांगली बातमी: {title} यांची {time} वाजता सुटका झाली असून ते {camp} येथे सुरक्षित आहेत. कृपया जुना संदेश पुढे पाठवू नका.",
        "hinglish": "Achhi khabar: {title} ko {time} baje bacha liya gaya tha, woh {camp} mein safe hain. Purana message aage forward mat kijiye.",
    },
    "verify": {
        "en": "We are checking this with official sources. Please don't forward it until it is confirmed.",
        "hi": "हम इस जानकारी की आधिकारिक स्रोतों से जाँच कर रहे हैं। पुष्टि होने तक इसे आगे न भेजें।",
        "mr": "आम्ही ही माहिती अधिकृत स्रोतांकडून तपासत आहोत. खात्री होईपर्यंत ती पुढे पाठवू नका.",
        "hinglish": "Hum is baat ko official sources se check kar rahe hain. Confirm hone tak forward mat kijiye.",
    },
    "stale": {
        "en": "Ticket {ticket} is still open and in the queue ({priority}). We have not forgotten you.",
        "hi": "टिकट {ticket} अभी खुला है और कतार में है ({priority})। हम आपको भूले नहीं हैं।",
        "mr": "तिकीट {ticket} अजून उघडे आहे आणि रांगेत आहे ({priority}). आम्ही तुम्हाला विसरलो नाही.",
        "hinglish": "Ticket {ticket} abhi khula hai aur line mein hai ({priority}). Hum aapko bhoole nahi hain.",
    },
    "supplies_ack": {
        "en": "Supplies request noted under ticket {ticket}. It will go to the supplies van, not a rescue boat.",
        "hi": "राहत सामग्री का अनुरोध टिकट {ticket} में दर्ज है। यह सामान वाली गाड़ी को भेजा जाएगा।",
        "mr": "मदत साहित्याची विनंती तिकीट {ticket} मध्ये नोंदवली आहे. ती साहित्य गाडीकडे पाठवली जाईल.",
        "hinglish": "Saamaan ki request ticket {ticket} mein darj hai. Yeh supplies van ko jayegi.",
    },
    "road_ack": {
        "en": "Thank you, we have noted the report about {road}.",
        "hi": "धन्यवाद, {road} के बारे में आपकी जानकारी दर्ज कर ली गई है।",
        "mr": "धन्यवाद, {road} बद्दलची तुमची माहिती नोंदवली आहे.",
        "hinglish": "Dhanyavaad, {road} ke baare mein aapki jaankari note kar li gayi hai.",
    },
    "info_ack": {
        "en": "Thank you, this has been noted for the control room.",
        "hi": "धन्यवाद, यह जानकारी कंट्रोल रूम में दर्ज कर ली गई है।",
        "mr": "धन्यवाद, ही माहिती कंट्रोल रूममध्ये नोंदवली आहे.",
        "hinglish": "Dhanyavaad, yeh jaankari control room mein note kar li gayi hai.",
    },
    "danger_noted": {
        "en": "The rescue team has been told about the danger.",
        "hi": "बचाव टीम को इस खतरे के बारे में बता दिया गया है।",
        "mr": "बचाव पथकाला या धोक्याबद्दल कळवले आहे.",
        "hinglish": "Rescue team ko is khatre ke baare mein bata diya gaya hai.",
    },
    "not_covered": {
        "en": "I don't have approved safety steps for this. Please call 112 now.",
        "hi": "इसके लिए मेरे पास स्वीकृत सुरक्षा निर्देश नहीं हैं। कृपया अभी 112 पर कॉल करें।",
        "mr": "यासाठी माझ्याकडे मंजूर सुरक्षा सूचना नाहीत. कृपया आत्ता 112 वर कॉल करा.",
        "hinglish": "Iske liye mere paas approved safety steps nahi hain. Abhi 112 par call kijiye.",
    },
    "call_now": {
        "en": "{number} – {label}: call now.",
        "hi": "{number} – {label}: अभी कॉल करें।",
        "mr": "{number} – {label}: आत्ता कॉल करा.",
        "hinglish": "{number} – {label}: abhi call kijiye.",
    },
    "also_call": {
        "en": "You can also call {number}.",
        "hi": "आप {number} पर भी कॉल कर सकते हैं।",
        "mr": "तुम्ही {number} वरही कॉल करू शकता.",
        "hinglish": "Aap {number} par bhi call kar sakte hain.",
    },
    "medical_emergency": {
        "en": "Ambulance",
        "hi": "एम्बुलेंस",
        "mr": "रुग्णवाहिका",
        "hinglish": "Ambulance",
    },
    "saathi_footer": {
        "en": "These steps are from the approved safety playbook.",
        "hi": "ये निर्देश स्वीकृत सुरक्षा पुस्तिका से हैं।",
        "mr": "या सूचना मंजूर सुरक्षा पुस्तिकेतून आहेत.",
        "hinglish": "Yeh steps approved safety playbook se hain.",
    },
    "faq_helplines": {
        "en": "Helplines: Emergency 112, Fire 101, Ambulance 108, LPG leak 1906, Disaster control room 1916.",
        "hi": "हेल्पलाइन: आपातकाल 112, फायर 101, एम्बुलेंस 108, एलपीजी लीक 1906, आपदा नियंत्रण कक्ष 1916।",
        "mr": "हेल्पलाइन: आपत्कालीन 112, अग्निशमन 101, रुग्णवाहिका 108, एलपीजी गळती 1906, आपत्ती नियंत्रण कक्ष 1916.",
        "hinglish": "Helpline: Emergency 112, Fire 101, Ambulance 108, LPG leak 1906, Disaster control room 1916.",
    },
    "faq_camps": {
        "en": "Relief camps open now: {camps}. Food, drinking water and first aid are available.",
        "hi": "अभी खुले राहत शिविर: {camps}। खाना, पीने का पानी और प्राथमिक उपचार उपलब्ध है।",
        "mr": "आत्ता सुरू असलेली मदत शिबिरे: {camps}. जेवण, पिण्याचे पाणी आणि प्रथमोपचार उपलब्ध आहे.",
        "hinglish": "Abhi khule relief camp: {camps}. Khana, peene ka paani aur first aid milega.",
    },
    "faq_family": {
        "en": "To check if a family is safe, open the 'Is my family safe?' page and search by ticket number or name and area.",
        "hi": "कोई परिवार सुरक्षित है या नहीं, यह जानने के लिए 'क्या मेरा परिवार सुरक्षित है?' पेज पर टिकट नंबर या नाम और इलाका डालें।",
        "mr": "कुटुंब सुरक्षित आहे का हे पाहण्यासाठी 'माझे कुटुंब सुरक्षित आहे का?' पानावर तिकीट क्रमांक किंवा नाव आणि परिसर शोधा.",
        "hinglish": "Family safe hai ya nahi, yeh 'Is my family safe?' page par ticket number ya naam aur area se dekhiye.",
    },
    "faq_unknown": {
        "en": "I can help with helplines, relief camps and what to do in a flood. For anything urgent, call 112.",
        "hi": "मैं हेल्पलाइन, राहत शिविर और बाढ़ में क्या करें, इसमें मदद कर सकता हूँ। किसी भी आपात स्थिति में 112 पर कॉल करें।",
        "mr": "मी हेल्पलाइन, मदत शिबिरे आणि पुरात काय करावे यात मदत करू शकतो. कोणत्याही तातडीच्या परिस्थितीत 112 वर कॉल करा.",
        "hinglish": "Main helpline, relief camp aur flood mein kya karein, isme madad kar sakta hoon. Emergency ho to 112 par call kijiye.",
    },
    "bulletin": {
        "en": "Ward 12 flood bulletin, {time}: Mithi river is near the danger level. Move to upper floors or to {camps}. Do not walk through moving water. Emergency 112.",
        "hi": "वार्ड 12 बाढ़ सूचना, {time}: मीठी नदी खतरे के निशान के पास है। ऊपरी मंज़िल पर या {camps} में जाएँ। बहते पानी में न चलें। आपातकाल 112।",
        "mr": "वॉर्ड 12 पूर सूचना, {time}: मिठी नदी धोक्याच्या पातळीजवळ आहे. वरच्या मजल्यावर किंवा {camps} येथे जा. वाहत्या पाण्यातून चालू नका. आपत्कालीन 112.",
        "hinglish": "Ward 12 flood bulletin, {time}: Mithi nadi khatre ke nishaan ke paas hai. Upar ki manzil par ya {camps} mein jaiye. Behte paani mein mat chaliye. Emergency 112.",
    },
}

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "hinglish": "Hinglish"}


def t(key, lang, **values):
    entry = TEMPLATES[key]
    text = entry.get(lang) or entry["en"]
    return text.format(**values)


def playbook_language(lang):
    """Playbooks exist in en, hi and mr. Hinglish speakers read Hindi best."""
    return {"hinglish": "hi"}.get(lang, lang if lang in ("en", "hi", "mr") else "en")
