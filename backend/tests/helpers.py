from app import db

KAMLA_VOICE = "पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे"
KAMLA_DAUGHTER = "Please help my mother Kamla Devi, Lane 4 behind Hanuman temple, Shanti Nagar. Water rising!!"
KAMLA_NEIGHBOUR = "shantinagar gali 4 mandir ke peeche budhi amma aur bachcha phase hai"

KAMLA_PHONE = "+91 90000 00412"
DAUGHTER_PHONE = "+91 90000 05101"
NEIGHBOUR_PHONE = "+91 90000 05102"


def at(hhmm):
    db.set_clock(db.game_time_on_night(hhmm), speed=0)


def outgoing(phone):
    r = db.one("SELECT id FROM reporters WHERE phone = ?", (phone,))
    return [m["text"] for m in db.query(
        "SELECT text FROM messages WHERE reporter_id = ? AND direction = 'out' AND status = 'sent' ORDER BY id", (r["id"],))]
