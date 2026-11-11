# Pukaar: 3-minute demo script

**Before you start (2 minutes, off stage)**

1. Set your own passwords (see *Signing in* in the README), run `./start.sh` (or `.\start.ps1` on Windows), open `http://localhost:8000/control` on the laptop and sign in as `rao`. (`http://localhost:8000` is the public landing page.)
2. In a second terminal run `cloudflared tunnel --url http://localhost:8000` and note the `https://….trycloudflare.com` address. Open that address once, so the dashboard's QR code shows the public link.
3. In a second browser window (a private window, so it has its own sign-in) open `/volunteer` and sign in as `boat1`. In a third, open `/chat` and pick **Kamla Devi**.
4. In the toolbar along the top of the map, set the replay speed to **10×** but don't start it.

The replay plays the flood night from 9:30 PM. At 10× a game minute takes 6 seconds. Pause whenever you need to talk.

---

**0:00 to 0:20. The problem (talk over the empty dashboard)**

> "India can push a flood alert to every phone. What comes back is chaos: the same family reported five times in three languages, rumours, and boats sent to people who were rescued hours ago. Pukaar turns every call for help into one ticket and closes it when the family is safe. Agents do the paperwork. Humans send the boats."

Press **▶ Start**.

**0:20 to 0:45. A red alert arrives (game time 9:35 PM)**

- The incident card in the left sidebar turns to **Red alert**. In the activity feed, Watch reads the CAP alert, checks Open-Meteo, marks two watch zones on the map and proposes pre-positioning Boats 2 and 3. Loop drafts Marathi and Hindi bulletins.
- Approve **Pre-position Boat 2**. Point out: *"Nothing moves without this tap. That's enforced in the backend, and there are tests for it."*

**0:45 to 1:15. Three messages, one family (9:38 to 9:44 PM)**

- Kamla's Hindi voice note arrives, then her daughter's English post from Pune, then the neighbour's Hinglish SMS.
- In the queue, P-0401 grows to **3 reports merged** and becomes **P1** with chips: *water at knee height, water rising, elder 68, child with fever*.
- Click the ticket: the raw messages sit beside the extraction, and each link has its reason (*"in English and Hindi, same family name, same landmark, same lane, 3 minutes apart"*).
- Show the chat window: Kamla got one follow-up in Hindi ("घर में कितने लोग हैं?"), answered "3 लोग", and was told her daughter's message is linked.

**1:15 to 1:35. Approve Boat 1**

- Press **❚❚ Pause**. On the approval card: *Send Boat 1 to Kamla Devi household?* with *Medic on board, 0.8 km, about 11 min, 3 h on duty*.
- Press **Approve**. In the volunteer window press **Accept**. The boat starts moving on the map; Kamla's chat shows "Boat 1 आपकी ओर आ रही है" and her OTP. Her daughter gets the same update in English.

**1:35 to 2:00. A judge messages live**

- Show the QR code in the map toolbar. A judge scans it, picks "I'm a new person" and sends anything: a rescue request in their own words, or "Where is the nearest relief camp?"
- Their message appears in the activity feed within a second, and they get a reply in their language.

**2:00 to 2:20. Saathi on a gas leak**

- In the chat window, switch to **Rukhsar Shaikh** and tap the sample *"गली 7 मस्जिद के पास गैस की बदबू आ रही है… क्या करें?"* (or wait for it in the replay at 10:20 PM).
- The reply starts with **"1906 – एलपीजी आपातकाल"**, then five steps copied from the gas-leak playbook. On the dashboard, the Shaikh ticket jumps to P1 with *Gas leak reported*, and the rescue team's task says DANGER: gas.

**2:20 to 2:40. Lane 6 floods**

- In the volunteer window press **Lane blocked → Lane 6** (the replay also does this itself at 11:10 PM).
- Lane 6 turns red on the map. Dispatch replans every route that used it, and the activity feed shows the old and new times. The family on a replanned route is told why their boat is taking longer.

**2:40 to 3:00. Closed means closed, and the family lookup**

- In the volunteer window press **Enter family OTP** and type the code from Kamla's chat. The ticket turns green: *Rescued at …, safe at Camp 3*. All three reporters are told, and Kamla is asked to reply 1 to close it.
- Open `/family`, search **Pinto**: *"Rescued at 8:12 PM, now at Camp 3"*. No address, no phone. Point at the activity feed: reposts about the Pintos get that same answer automatically, so no boat goes there.

> "One family, one ticket, one closing."

---

**If something goes wrong**

- Ollama is slow or stopped: the LLM chip in the map toolbar shows *unavailable · rules* and everything keeps working.
- Something looks stuck: **Reset** (the circular arrow in the map toolbar) restarts the night. Automation off (the red switch) shows that agents keep logging while sending nothing.
- No internet: the map tiles go blank but everything else works. Rainfall falls back to the scenario's figures.
