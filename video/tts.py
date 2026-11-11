"""Speak the narration with Kokoro, offline, and lay it out on a timeline.

Each line gets its own speed (the modulation: slow and low for the flood,
brisker for the live demo and the code) and a pause after it. Output:
  build/audio/<n>.wav   one clip per line
  build/lines.json      start, end and caption text for every line
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

HERE = Path(__file__).parent
BUILD = HERE / "build"
SR = 24000
LEAD_IN = 0.8  # seconds of picture before the first word

script = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
kokoro = Kokoro(str(HERE / "models" / "kokoro-v1.0.onnx"), str(HERE / "models" / "voices-v1.0.bin"))
(BUILD / "audio").mkdir(parents=True, exist_ok=True)

t = LEAD_IN
prev_scene = None
out = []
for i, line in enumerate(script["lines"]):
    if prev_scene and line["scene"] != prev_scene:
        t += 0.45  # a breath between scenes, for the transition
    hindi = line.get("voice") == "hindi"
    voice = script["hindi_voice"] if hindi else script["narrator"]
    samples, sr = kokoro.create(line.get("say", line["text"]), voice=voice, speed=line["speed"], lang="hi" if hindi else "en-us")
    assert sr == SR
    # Trim silence Kokoro leaves at the ends, then a short fade so clips never click.
    a = np.asarray(samples, dtype=np.float32)
    nz = np.flatnonzero(np.abs(a) > 0.01)
    if len(nz):
        a = a[max(nz[0] - 240, 0): nz[-1] + 1200]
    fade = min(240, len(a) // 4)
    a[:fade] *= np.linspace(0, 1, fade)
    a[-fade:] *= np.linspace(1, 0, fade)
    path = BUILD / "audio" / f"{i:02d}.wav"
    sf.write(path, a, SR)
    dur = len(a) / SR
    out.append({"i": i, "scene": line["scene"], "start": round(t, 3), "end": round(t + dur, 3),
                "caption": line.get("caption", line["text"]), "hindi": hindi,
                "agent": line.get("agent"), "beat": line.get("beat"), "file": path.name})
    print(f"{i:02d} {line['scene']:8s} {t:7.2f}s +{dur:5.2f}s  {line['text'][:60]}")
    t += dur + line["pause"]
    prev_scene = line["scene"]

total = round(t + 1.0, 2)
(BUILD / "lines.json").write_text(json.dumps({"total": total, "lines": out}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"total {total:.1f}s")
