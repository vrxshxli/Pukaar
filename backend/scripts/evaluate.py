"""Run the generated flood night through Pukaar and through a first-come-first-served
baseline, and write docs/eval-report.md with the real numbers.

Usage:
  python scripts/evaluate.py                 # rules mode, plus Ollama if it is available
  python scripts/evaluate.py --modes rules
  python scripts/evaluate.py --modes rules ollama

How Pukaar is run: every message goes through the real orchestrator at its time on
the game clock, and the clock advances one minute at a time so teams move. A
simulated duty officer approves dispatch, pre-positioning and bulletin proposals
one minute after they appear. For "Possible duplicate" cards the officer reads the
raw messages, which we model with the ground truth; merge scores are reported both
before and after that review, so the automatic part is visible on its own.

How the baseline is run: every request message is a new job, and the three boats
take jobs strictly in arrival order (no merging, no priority, no verify lane).
Boats travel on the same road graph at the same speed, spend the same time on
scene, and drop families at the nearest camp. No typing time is added, which
flatters the baseline.
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import db, llm, orchestrator, scenario  # noqa: E402
from app.tools import approvals, geo  # noqa: E402

NIGHT = json.loads((ROOT / "data" / "scenario" / "flood_night.json").read_text(encoding="utf-8"))
REPORT = ROOT.parent / "docs" / "eval-report.md"
REQUEST_KINDS = ("rescue", "welfare", "supplies", "repost_safe")
OFFICER_DELAY_MIN = 1
ON_SCENE_MIN = 4
INTENT_OF_KIND = {"rescue": "rescue", "welfare": "welfare", "supplies": "supplies", "rumour": "rumour",
                  "question": "question", "faq": "faq", "road": "road_report", "power": "power_report",
                  "status": "status_query", "safe": "safe_report", "repost_safe": "rescue"}


def t(iso):
    return datetime.fromisoformat(iso)


def items():
    out = [{"kind": "message", **m} for m in NIGHT["messages"]] + [{"kind": "event", **e} for e in NIGHT["events"]]
    return sorted(out, key=lambda i: i["time"])


# Running Pukaar.

def run_pukaar(mode):
    tmp = Path(tempfile.mkdtemp()) / "eval.db"
    os.environ["PUKAAR_DB"] = str(tmp)
    db.connect(tmp)
    db.set_setting("llm_mode", mode)
    db.set_setting("auto_field", "on")
    if mode == "ollama" and not llm.check_health(force=True):
        return None
    message_truth = {}
    queue = items()
    clock = t(NIGHT["start"])
    end = t(NIGHT["end"]) + timedelta(minutes=90)
    started = time.time()
    i = 0
    while clock <= end:
        while i < len(queue) and t(queue[i]["time"]) <= clock:
            item = queue[i]
            db.set_clock(t(item["time"]), speed=0)
            if item["kind"] == "message":
                orchestrator.handle_message(item["phone"], item["text"], channel=item["channel"], name=item.get("sender"))
                last = db.one("SELECT MAX(id) AS id FROM messages WHERE direction = 'in'")["id"]
                message_truth[last] = item
            else:
                orchestrator.handle_volunteer(item["team"], item["action"], road=item.get("road"))
            i += 1
        db.set_clock(clock, speed=0)
        simulated_officer(clock, message_truth)
        orchestrator.tick()
        clock += timedelta(minutes=1)
    return {"mode": mode, "seconds": round(time.time() - started, 1), "message_truth": message_truth,
            "llm": llm.status() if mode == "ollama" else None}


def simulated_officer(clock, message_truth):
    for a in approvals.pending():
        if t(a["created_at"]) > clock - timedelta(minutes=OFFICER_DELAY_MIN):
            continue
        if a["kind"] == "merge":
            same = ticket_family(a["ticket_id"], message_truth) == ticket_family(a["payload"]["into"], message_truth)
            orchestrator.handle_approval(a["id"], "approve" if same else "reject", "Simulated officer")
        elif a["kind"] in ("dispatch", "preposition", "bulletin"):
            try:
                orchestrator.handle_approval(a["id"], "approve", "Simulated officer")
            except ValueError:
                pass


def report_truth(message_truth):
    """report id -> truth item, through the message each report came from."""
    out = {}
    for r in db.query("SELECT id, message_id FROM reports"):
        if r["message_id"] in message_truth:
            out[r["id"]] = message_truth[r["message_id"]]
    return out


def ticket_family(ticket_id, message_truth):
    rt = report_truth(message_truth)
    fams = [rt[l["report_id"]]["truth"]["family"] for l in
            db.query("SELECT report_id FROM ticket_reports WHERE ticket_id = ?", (ticket_id,)) if l["report_id"] in rt]
    return Counter(fams).most_common(1)[0][0] if fams else None


def score_pukaar(run):
    mt = run["message_truth"]
    rt = report_truth(mt)
    links = db.query("SELECT ticket_id, report_id, reason FROM ticket_reports")
    final_ticket, auto_ticket = {}, {}
    for l in links:
        final_ticket[l["report_id"]] = l["ticket_id"]
        reason = l["reason"] or ""
        # Reports moved by the officer still count under their original ticket for the automatic score.
        auto_ticket[l["report_id"]] = reason.split("merged by officer from ")[1] if "merged by officer from" in reason else l["ticket_id"]

    request_reports = [rid for rid, item in rt.items() if item["truth"]["kind"] in REQUEST_KINDS]
    merge_final = pair_scores(request_reports, rt, final_ticket)
    merge_auto = pair_scores(request_reports, rt, auto_ticket)

    fields = field_accuracy(rt)
    intents = intent_accuracy(rt)

    approved = db.query("""SELECT * FROM approvals WHERE kind = 'dispatch' AND status = 'approved' ORDER BY decided_at""")
    first_assign = {}
    trips = Counter()
    wasted = []
    family_served = set()
    for a in approved:
        fam = ticket_family(a["ticket_id"], mt)
        payload = db.loads(a["payload"], {})
        kind = NIGHT["families"].get(fam, {}) if fam else {}
        if fam and fam not in first_assign:
            first_assign[fam] = a["decided_at"]
        if payload.get("support"):
            trips["medic backup"] += 1
            continue
        if fam is None or fam.startswith("rumour"):
            wasted.append(("rumour or unknown", a["ticket_id"]))
        elif kind.get("already_safe"):
            wasted.append(("family already rescued", a["ticket_id"]))
        elif fam in family_served:
            wasted.append(("duplicate of a family already served", a["ticket_id"]))
        family_served.add(fam)
        trips["total"] += 1

    p1 = p1_assign_times(first_assign)
    rumour_reports = [rid for rid, item in rt.items() if item["truth"]["rumour"]]
    verify_tickets = {r["id"] for r in db.query("SELECT id FROM tickets WHERE kind = 'verify'")}
    caught = sum(1 for rid in rumour_reports if final_ticket.get(rid) in verify_tickets)
    false_verify = sum(1 for rid, item in rt.items() if not item["truth"]["rumour"] and final_ticket.get(rid) in verify_tickets)
    reposts = [rid for rid, item in rt.items() if item["truth"]["kind"] == "repost_safe"]
    reposts_answered = sum(1 for rid in reposts if final_ticket.get(rid) == "P-0398")
    tickets_after = db.one("""SELECT COUNT(*) n FROM tickets WHERE kind IN ('rescue','welfare','supplies')
                              AND id != 'P-0398'""")["n"]
    outgoing = db.one("SELECT COUNT(*) n FROM messages WHERE direction = 'out' AND status = 'sent'")["n"]
    reporters_updated = db.one("""SELECT COUNT(DISTINCT reporter_id) n FROM messages WHERE direction = 'out'
                                  AND status = 'sent' AND kind IN ('status','auto_reply','followup')""")["n"]
    reporters = db.one("SELECT COUNT(*) n FROM reporters")["n"]
    return {
        "merge_final": merge_final, "merge_auto": merge_auto, "fields": fields, "intents": intents,
        "p1": p1, "trips": trips["total"], "medic_backup": trips["medic backup"], "wasted": wasted,
        "rumours": (caught, len(rumour_reports)), "false_verify": false_verify,
        "reposts": (reposts_answered, len(reposts)), "tickets_after": tickets_after,
        "reports_in": len(mt), "outgoing": outgoing, "reporters_updated": (reporters_updated, reporters),
        "merge_cards": db.one("SELECT COUNT(*) n FROM approvals WHERE kind = 'merge'")["n"],
    }


def pair_scores(report_ids, rt, ticket_of):
    tp = fp = fn = 0
    ids = sorted(report_ids)
    for a_i, a in enumerate(ids):
        for b in ids[a_i + 1:]:
            fa, fb = rt[a]["truth"]["family"], rt[b]["truth"]["family"]
            truth_same = fa is not None and fa == fb
            ta, tb = ticket_of.get(a), ticket_of.get(b)
            pred_same = ta is not None and ta == tb
            tp += truth_same and pred_same
            fp += pred_same and not truth_same
            fn += truth_same and not pred_same
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def field_accuracy(rt):
    totals, right = Counter(), Counter()
    for rid, item in rt.items():
        truth = item["truth"]
        if truth["kind"] not in ("rescue", "welfare"):
            continue
        row = db.one("SELECT fields FROM reports WHERE id = ?", (rid,))
        f = db.loads(row["fields"], {})
        tf = truth["fields"]
        checks = {
            "language": f.get("language") == item["language"],
            "people": (f.get("people") == tf["people"]) if tf.get("people") else (not f.get("people") or f.get("people_implied")),
            "vulnerable": set(f.get("vulnerable", [])) == set(tf.get("vulnerable", [])),
            "medical": set(f.get("medical", [])) == set(tf.get("medical", [])),
            "water level": f.get("water_level") == tf.get("water"),
            "location (lane)": (f.get("lane") == tf.get("lane")) if tf.get("lane") else not f.get("location_found"),
        }
        if tf.get("danger"):
            checks["danger"] = set(f.get("danger", [])) >= set(tf["danger"])
        for k, ok in checks.items():
            totals[k] += 1
            right[k] += bool(ok)
    per_field = {k: right[k] / totals[k] for k in totals}
    overall = sum(right.values()) / sum(totals.values()) if totals else 0
    return {"per_field": per_field, "overall": overall, "messages": totals["language"]}


def intent_accuracy(rt):
    total = right = 0
    confusion = Counter()
    for rid, item in rt.items():
        kind = item["truth"]["kind"]
        if kind not in INTENT_OF_KIND:
            continue
        f = db.loads(db.one("SELECT fields FROM reports WHERE id = ?", (rid,))["fields"], {})
        total += 1
        if f.get("intent") == INTENT_OF_KIND[kind]:
            right += 1
        else:
            confusion[(kind, f.get("intent"))] += 1
    return {"accuracy": right / total if total else 0, "total": total, "top_misses": confusion.most_common(5)}


def p1_families():
    first = {}
    for m in NIGHT["messages"]:
        tr = m["truth"]
        if tr["priority"] == "P1" and tr["family"] and tr["kind"] in ("rescue", "welfare"):
            first.setdefault(tr["family"], m["time"])
    return first


def p1_assign_times(first_assign):
    first_msg = p1_families()
    waits = []
    for fam, first in first_msg.items():
        if fam in first_assign:
            waits.append((t(first_assign[fam]) - t(first)).total_seconds() / 60)
    return {"families": len(first_msg), "assigned": len(waits),
            "median": statistics.median(waits) if waits else None,
            "p90": sorted(waits)[int(len(waits) * 0.9) - 1] if len(waits) >= 2 else (waits[0] if waits else None)}


# The first-come-first-served baseline.

def request_node(m):
    lane = m["truth"]["fields"].get("lane")
    fam = NIGHT["families"].get(m["truth"]["family"] or "", {})
    if m["truth"]["kind"] == "supplies":
        g = geo.geocode_landmark(m["text"])
        return g["node"] if g["found"] else None
    if fam.get("landmark") and lane:
        return scenario.landmark_by_id(fam["landmark"])["node"]
    if lane == "Sector 3":
        return "sector3"
    if lane and lane.startswith("Lane"):
        node = f"L{lane.split()[1]}_mid"
        return node if node in geo.nodes() else None
    return None


def run_baseline():
    boats = [{"id": tm["id"], "node": tm["node"], "free_at": t(NIGHT["start"])} for tm in scenario.teams() if tm["kind"] == "boat"]
    blocked_from = t(NIGHT["events"][0]["time"])
    jobs = []
    for m in NIGHT["messages"]:
        kind = m["truth"]["kind"]
        if kind in REQUEST_KINDS or (kind == "followup" and m["truth"]["fields"].get("lane")):
            node = request_node(m)
            if node:
                jobs.append({"time": t(m["time"]), "node": node, "family": m["truth"]["family"], "kind": kind})
    jobs.sort(key=lambda j: j["time"])
    rescued_at, first_assign = {}, {}
    wasted, supplies_on_boats, trips = [], 0, 0
    for job in jobs:
        boat = min(boats, key=lambda b: b["free_at"])
        start = max(job["time"], boat["free_at"])
        blocked = ["Lane 6"] if start >= blocked_from else []
        path = geo.shortest_path(boat["node"], job["node"], blocked) or geo.shortest_path(boat["node"], job["node"])
        travel = geo.LAUNCH_MIN + path["cost_m"] / geo.BOAT_METRES_PER_MIN
        arrive = start + timedelta(minutes=travel)
        fam = job["family"]
        trips += 1
        first_assign.setdefault(fam, start.isoformat())
        if job["kind"] == "supplies":
            supplies_on_boats += 1
        if fam == "pinto":
            wasted.append("family already rescued")
        elif fam in rescued_at and rescued_at[fam] <= arrive:
            wasted.append("duplicate of a family already served")
        else:
            rescued_at.setdefault(fam, arrive)
        camp_paths = [geo.shortest_path(job["node"], c["node"], blocked) for c in scenario.camps()]
        camp_path = min((p for p in camp_paths if p), key=lambda p: p["cost_m"])
        back = geo.LAUNCH_MIN + camp_path["cost_m"] / geo.BOAT_METRES_PER_MIN
        boat["free_at"] = arrive + timedelta(minutes=ON_SCENE_MIN + back)
        boat["node"] = camp_path["nodes"][-1]
    rumour_messages = sum(1 for m in NIGHT["messages"] if m["truth"]["rumour"])
    return {"p1": p1_assign_times(first_assign), "trips": trips, "wasted": wasted,
            "supplies_on_boats": supplies_on_boats, "tickets_after": len(jobs), "rumours": (0, rumour_messages),
            "last_boat_free": max(b["free_at"] for b in boats)}


# Writing the report.

def pct(x):
    return f"{x * 100:.1f}%"


def mins(x):
    return "n/a" if x is None else f"{x:.0f} min"


def write_report(results, baseline, skipped):
    kinds = Counter(m["truth"]["kind"] for m in NIGHT["messages"])
    langs = Counter(m["language"] for m in NIGHT["messages"])
    lines = [
        "# Pukaar evaluation report",
        "",
        f"Generated by `backend/scripts/evaluate.py` on the synthetic flood night (seed {NIGHT['seed']}): "
        f"{len(NIGHT['messages'])} messages from 9:30 PM to 2:30 AM, "
        + ", ".join(f"{n} {k}" for k, n in sorted(langs.items())) + " (by language code). "
        "These are the real numbers from this run, not targets.",
        "",
        "Message mix: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())) + ".",
        "",
        "## Headline: Pukaar against first-come-first-served",
        "",
        "| Measure | First-come-first-served | " + " | ".join(f"Pukaar ({r['label']})" for r in results) + " |",
        "| --- | --- | " + " | ".join("---" for _ in results) + " |",
    ]

    def row(name, base, fn):
        lines.append(f"| {name} | {base} | " + " | ".join(fn(r) for r in results) + " |")

    row("Requests turned into jobs or tickets", str(baseline["tickets_after"]), lambda r: str(r["score"]["tickets_after"]))
    row("Duplicate-merge F1 (after officer review)", "0 (no merging)", lambda r: f"{r['score']['merge_final']['f1']:.2f}")
    row("Median time to assign a P1 family", mins(baseline["p1"]["median"]), lambda r: mins(r["score"]["p1"]["median"]))
    row("90th percentile time to assign a P1 family", mins(baseline["p1"]["p90"]), lambda r: mins(r["score"]["p1"]["p90"]))
    row("P1 families assigned by the end", f"{baseline['p1']['assigned']}/{baseline['p1']['families']}",
        lambda r: f"{r['score']['p1']['assigned']}/{r['score']['p1']['families']}")
    row("Boat or van trips", str(baseline["trips"]), lambda r: str(r["score"]["trips"]))
    row("Wasted trips (already rescued, rumour or duplicate)", str(len(baseline["wasted"])), lambda r: str(len(r["score"]["wasted"])))
    row("Supplies requests sent on rescue boats", str(baseline["supplies_on_boats"]), lambda r: "0 (van only)")
    row("Rumours caught in the Verify lane", f"0/{baseline['rumours'][1]}",
        lambda r: f"{r['score']['rumours'][0]}/{r['score']['rumours'][1]}")
    lines.append("")
    for r in results:
        s = r["score"]
        lines += [
            f"## Pukaar in {r['label']} mode",
            "",
            f"Run time: {r['seconds']} s for the whole night." + (f" Model: {r['model']}." if r.get("model") else ""),
            "",
            "**Duplicate merging** (pairs of request messages about the same family):",
            "",
            "| | Precision | Recall | F1 | True pairs found | Wrong merges | Missed pairs |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            f"| Automatic merges only | {s['merge_auto']['precision']:.2f} | {s['merge_auto']['recall']:.2f} | "
            f"{s['merge_auto']['f1']:.2f} | {s['merge_auto']['tp']} | {s['merge_auto']['fp']} | {s['merge_auto']['fn']} |",
            f"| After the officer reviews {s['merge_cards']} 'possible duplicate' cards | {s['merge_final']['precision']:.2f} | "
            f"{s['merge_final']['recall']:.2f} | {s['merge_final']['f1']:.2f} | {s['merge_final']['tp']} | "
            f"{s['merge_final']['fp']} | {s['merge_final']['fn']} |",
            "",
            f"**Field extraction** on {s['fields']['messages']} rescue and welfare messages: "
            f"{pct(s['fields']['overall'])} of fields correct overall.",
            "",
            "| Field | Accuracy |",
            "| --- | --- |",
        ]
        lines += [f"| {k} | {pct(v)} |" for k, v in s["fields"]["per_field"].items()]
        lines += [
            "",
            f"**Intent** (what kind of message it is) correct for {pct(s['intents']['accuracy'])} of "
            f"{s['intents']['total']} messages."
            + (" Most common misses: " + "; ".join(f"{a} read as {b} ({n})" for (a, b), n in s["intents"]["top_misses"]) + "."
               if s["intents"]["top_misses"] else ""),
            "",
            f"**Other measures:** {s['rumours'][0]} of {s['rumours'][1]} rumour messages went to Verify, and "
            f"{s['false_verify']} genuine messages were wrongly sent there. {s['reposts'][0]} of {s['reposts'][1]} reposts "
            f"about the already-rescued Pinto family were matched to their closed ticket and answered automatically. "
            f"{s['reporters_updated'][0]} of {s['reporters_updated'][1]} reporters received at least one status update or "
            f"question back. {s['medic_backup']} medic backup trips were requested.",
            "",
        ]
        if s["wasted"]:
            lines.append("Wasted trips: " + "; ".join(f"{why} ({tid})" for why, tid in s["wasted"]) + ".")
            lines.append("")
    if skipped:
        lines += ["## Not run", "", skipped, ""]
    lines += [
        "## How this was measured",
        "",
        "- Ground truth comes from the generator: each message knows its family, kind, true priority and stated fields. "
        "True priority uses a separate rubric in `generate_flood_night.py`, not Triage's scoring rules.",
        f"- A simulated officer approves dispatches, pre-positioning and bulletins {OFFICER_DELAY_MIN} minute after they appear. "
        "For 'possible duplicate' cards it uses the ground truth, standing in for an officer reading the raw messages; "
        "the automatic-only merge row shows the score without that help.",
        f"- Volunteers accept tasks after 1 minute and confirm the OTP {ON_SCENE_MIN} minutes after arriving.",
        "- The baseline sends the three boats to every request message in arrival order. It adds no typing time and "
        "ignores rumours entirely, which makes it look better than a real control room. Supplies requests go on boats "
        "because nothing separates them.",
        "- 'Time to assign' runs from a family's first message to the first approved dispatch (Pukaar) or the moment a "
        "boat takes the job (baseline).",
        "- Field accuracy counts a field as correct when it matches what the message actually says, including "
        "'not stated'. A people count that Listen marks as implied counts as not stated.",
        "- Caution on field accuracy: the generator builds messages from phrase templates, and the rules extractor "
        "was written by the same team with the same vocabulary in mind, so rules-mode field accuracy here is an upper "
        "bound. Real messages are messier (typos, mixed scripts, missing words) and will score lower.",
        "- Merging and timing results depend on how crowded the ward is: this night has about 70 families on nine lanes, "
        "so many unrelated families share a lane and landmark, which is the hard case for merging.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="+", default=["rules", "ollama"])
    args = parser.parse_args()
    baseline = run_baseline()
    results, skipped = [], ""
    for mode in args.modes:
        print(f"Running Pukaar in {mode} mode...")
        run = run_pukaar(mode)
        if run is None:
            skipped = (f"Ollama mode was not run: {llm.status().get('last_error') or 'Ollama unreachable'}. "
                       f"Pull the model with `ollama pull {llm.chat_model()}` and run the evaluator again.")
            print(skipped)
            continue
        score = score_pukaar(run)
        label = mode if mode == "rules" else f"Ollama, {llm.chat_model()}"
        status = run.get("llm") or {}
        results.append({"label": label, "seconds": run["seconds"], "score": score,
                        "model": f"{llm.chat_model()} ({status.get('calls', 0)} model calls, "
                                 f"{status.get('fallbacks', 0)} fell back to rules)" if mode == "ollama" else None})
        print(f"  merge F1 auto {score['merge_auto']['f1']:.2f}, after review {score['merge_final']['f1']:.2f}; "
              f"fields {pct(score['fields']['overall'])}; P1 median {mins(score['p1']['median'])}; "
              f"wasted {len(score['wasted'])}")
    print(f"Baseline: P1 median {mins(baseline['p1']['median'])}, wasted {len(baseline['wasted'])}")
    write_report(results, baseline, skipped)


if __name__ == "__main__":
    main()
