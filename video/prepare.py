"""Prepare everything the composition needs.

- Splits every recording into numbered JPEG frames (build/frames/<clip>/<page>/000001.jpg).
- Writes build/data.js with the voiceover timeline, tap events, frame counts,
  real messages from the flood night, the real project tree and real code.
"""
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).parent
ROOT = HERE.parent
REC = HERE / "recordings"
BUILD = HERE / "build"
FPS = 25
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

clips = {}
for webm in sorted(REC.glob("*/*.webm")):
    clip, page = webm.parent.name, webm.stem
    out = BUILD / "frames" / clip / page
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(webm), "-vf", f"fps={FPS}", "-q:v", "3", str(out / "%06d.jpg")], check=True)
    n = len(list(out.glob("*.jpg")))
    w, h = (1600, 900) if page in ("desk", "dash") else (390, 844)
    clips.setdefault(clip, {})[page] = {"frames": n, "w": w, "h": h}
    print(f"{clip}/{page}: {n} frames")

rec = json.loads((REC / "events.json").read_text(encoding="utf-8"))
# Put every page of a clip on the clock of the clip's first page.
offsets = {}
for p in rec["pages"]:
    first = min(q["t0"] for q in rec["pages"] if q["clip"] == p["clip"])
    offsets[(p["clip"], p["page"])] = round(p["t0"] - first, 3)
for clip, pages in clips.items():
    for page, info in pages.items():
        info["offset"] = offsets.get((clip, page), 0)

night = json.loads((ROOT / "backend" / "data" / "scenario" / "flood_night.json").read_text(encoding="utf-8"))
messages = [m["text"] for m in night["messages"] if 18 < len(m["text"]) < 90][:60:2]

approvals = (ROOT / "backend" / "app" / "tools" / "approvals.py").read_text(encoding="utf-8").splitlines()
start = next(i for i, l in enumerate(approvals) if l.startswith("def require_approved"))
end = next(i for i in range(start + 1, len(approvals)) if approvals[i] and not approvals[i].startswith((" ", "\t")))
code_guard = "\n".join(approvals[start:end]).rstrip()

teams_src = (ROOT / "backend" / "app" / "tools" / "teams.py").read_text(encoding="utf-8").splitlines()
a = next(i for i, l in enumerate(teams_src) if l.startswith("def set_status"))
b = next(i for i in range(a + 1, len(teams_src)) if teams_src[i] and not teams_src[i].startswith((" ", "\t")))
code_assign = "\n".join(teams_src[a:b]).rstrip()

tree = [
    "pukaar/",
    "├─ backend/",
    "│  ├─ app/",
    "│  │  ├─ orchestrator.py     the planner: routes every event",
    "│  │  ├─ agents/             one file per agent",
    "│  │  │  └─ listen · triage · dispatch · loop · saathi · watch",
    "│  │  ├─ tools/              the only way agents touch the world",
    "│  │  │  ├─ approvals.py     the human gate",
    "│  │  │  └─ audit.py         every call on record",
    "│  │  └─ main.py · auth.py · llm.py",
    "│  └─ tests/                67 tests, every safety rule",
    "├─ frontend/src/",
    "│  ├─ pages/                landing · control · chat · volunteer · family",
    "│  └─ components/           map · queue · approval card",
    "├─ docs/                    architecture · eval report · demo script",
    "└─ video/                   this film, rendered from code",
]

lines = json.loads((BUILD / "lines.json").read_text(encoding="utf-8"))
data = {"fps": FPS, "clips": clips, "events": rec["events"], "timeline": lines, "messages": messages,
        "code": {"guard": code_guard, "assign": code_assign}, "tree": tree}
(BUILD / "data.js").write_text("window.DATA = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
print("data.js written;", len(messages), "messages;", "guard", len(code_guard.splitlines()), "lines;", "assign", len(code_assign.splitlines()), "lines")
