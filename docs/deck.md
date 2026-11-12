# Pukaar: 6-slide deck content

Team Seekers · AgentX Hackathon 2026 · PS-03

---

## Slide 1 · The problem and the user

**Title:** One duty officer. Three boats. 311 messages.

- **User:** the ward duty officer in a flood control room (Ward 12, Shanti Nagar, Mumbai).
- **Problem, in two sentences:** In a flood, the control room gets hundreds of messages at once: the same family three times, rumours, voice notes in Hindi, Marathi and English. Boats go in the order calls arrive, so the families in most danger wait the longest.
- **The number:** first come, first served leaves the most urgent families waiting a median of **463 minutes** on our test night.

*Visual:* the cold-open frame of messages flooding the screen, with the 463-minute stat.

---

## Slide 2 · Why an agent, not a chatbot

**Title:** A chatbot answers one person. The officer needs something that acts across the ward.

| A chatbot | Pukaar's agent |
| --- | --- |
| Replies to the person who wrote | Works on every message for the whole ward |
| Forgets after the chat | Reads short-term, long-term and episodic memory |
| Says what to do | Calls tools: finds matches, opens or merges tickets, scores, escalates, reroutes |
| Cannot be stopped mid-way | Every step validated; the officer approves every boat |

*Line:* Agents do the paperwork. Humans send the boats.

---

## Slide 3 · Agent design

**Title:** Plan → one tool → observe → replan, inside guardrails.

*Diagram:*

```
event ──► LLM Planner ──► plan (ordered tool calls + reasons)
              ▲                │
              │ observe        ▼
              └──────── one registry tool ── validated (allowed? schema? state?)
                               │                     └─ invalid / timeout / rate limit → rules take over (logged)
   memory (read-only)          ▼
   short-term · long-term ─►  proposal ──► officer approves (require_approved) ──► boat · OTP · safe
   episodic
```

- Free LLM: Groq free tier (live app) or Ollama locally; rules when neither is available.
- Planner only for judgment events (`PLANNER_SCOPE=judgment`); obvious ones stay rules, to stay inside free limits.
- No reachable tool dispatches, closes, downgrades or sends a bulletin. Merges only above the matcher's 0.6 score. P1 never lowered.

---

## Slide 4 · Live demo

**Title:** Kamla's rescue, live.

Screenshots (from `docs/screenshots/`, or frames from the film):

1. Kamla's Hindi voice note on her phone.
2. Control room: the **Agent reasoning** tab: plan, `find_similar_tickets`, `merge_into_ticket` (score 1.05), `score_priority` → **P1, 72 points**.
3. Approval card: "Send Boat 1 (medic), 0.8 km, about 11 min" → officer taps Approve.
4. Crew phone accepts; Kamla's phone gets the OTP 9055 at the same moment; family confirmed safe.

Links: live app https://pukaar.onrender.com · video (under 3 min).

---

## Slide 5 · Results and honest limits

**Title:** Same 311-message night, first come vs Pukaar.

| Measure | First come | Pukaar (rules) | Pukaar (LLM Planner) |
| --- | --- | --- | --- |
| Median time to assign a P1 family | 463 min | 20 min | 20 min |
| Wasted trips | 131 | 15 | 15 |
| Rumours caught | 0/15 | 15/15 | 15/15 |
| Boat or van trips | 210 | 56 | 55 |
| Duplicate-merge F1 | 0 | 0.79 | 0.76 |

The LLM Planner matches rules on outcomes; merge F1 0.76 vs 0.79. Of 200 runs, 72 finished on the model's own plan; 126 steps were rejected by the guardrails (48 weak merges, 19 rescue calls sent to Verify, 12 merges into a safe family, 2 rumours as rescue tickets, 45 invalid values) and the rules finished those events. Evaluated with a free local model, because a full night exceeds any free hosted tier.

**Honest limits:**
- A synthetic night, not field data; rules-mode field accuracy is an upper bound.
- Pukaar reached 25 of 28 P1 families in the window; the baseline reaches 28 only by running ~21 hours longer.
- Small models (3B) often stop early; the guardrails catch it and rules finish the job.
- Hindi and Marathi templates need a native-speaker review.

---

## Slide 6 · Impact and beyond floods

**Title:** Same agent. New map. New playbooks.

- **Impact:** urgent families reached in minutes, not hours; no boat wasted on a rumour; every decision on record with the officer's name.
- **Runs anywhere:** one laptop, free tools, works offline in rules mode.
- **Beyond floods:**
  - Cyclone: Watch pre-positions boats before landfall.
  - Earthquake: Triage ranks trapped and injured people.
  - Heatwave: Saathi sends people to cooling centres.
  - Urban fire: Dispatch routes crews around smoke.
- **Ask:** pilot with one ward control room in the next monsoon.

*Closing line:* Pukaar means "a call for help". We make sure every one is answered.
