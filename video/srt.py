"""Write the captions as an .srt file next to the film (for YouTube or any player)."""
import json
from pathlib import Path

HERE = Path(__file__).parent
tl = json.loads((HERE / "build" / "lines.json").read_text(encoding="utf-8"))


def stamp(s):
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int(round((sec % 1) * 1000)) % 1000:03d}"


out = []
lines = tl["lines"]
for i, l in enumerate(lines, 1):
    end = min(l["end"] + 0.6, lines[i]["start"] - 0.05) if i < len(lines) else l["end"] + 1
    out.append(f"{i}\n{stamp(l['start'])} --> {stamp(end)}\n{l['caption']}\n")
(HERE / "out").mkdir(exist_ok=True)
(HERE / "out" / "pukaar-demo.srt").write_text("\n".join(out), encoding="utf-8")
print(len(out), "captions")
