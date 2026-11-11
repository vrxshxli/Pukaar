# Pukaar demo film

A 4 minute 41 second film about Pukaar, rendered entirely from code: real screen recordings of the running app, motion graphics, an offline voiceover and burned-in captions.

Watch it: https://youtu.be/TGQ5zi1kfI8

Output: `out/pukaar-demo.mp4` (1920×1080, 30 fps, H.264 + AAC) and `out/pukaar-demo.srt`.

## How it is made

| Step | Script | What it does |
| --- | --- | --- |
| 1 | `record.py` | Drives the real app at `http://localhost:8000` in headless Chromium and records the control room, Kamla's phone and Boat 1's phone **at the same time**, plus the landing page, sign-in, hard cases, family lookup and a 10× replay. Logs every tap with its time and position. |
| 2 | `tts.py` | Speaks `narration.json` with Kokoro, fully offline (no text leaves the laptop). Each line has its own speed for modulation; Kamla's line uses a Hindi voice. |
| 3 | `mix.py` | Mixes the voice with a synthesised ambient pad that ducks under speech, rain for the cold open, whooshes on scene changes and two accent hits. No licensed audio. |
| 4 | `prepare.py` | Splits recordings into frames and bundles the timeline, tap events, real flood-night messages, the project tree and real code from `backend/app/tools/` into `build/data.js`. |
| 5 | `compose/` | The film itself: an HTML page where every frame is a pure function of time. Scenes, device mockups, camera zooms, tap ripples, kinetic type and word-by-word captions. |
| 6 | `render.py` | Seeks the composition frame by frame, screenshots each one and pipes them into ffmpeg with the soundtrack. `--stills 12,95` saves single frames for checking. |
| 7 | `srt.py` | Writes the captions as an `.srt` file. |

## Re-render

```bash
cd video
python -m venv .venv && .venv/Scripts/python -m pip install playwright==1.49.1 imageio-ffmpeg kokoro-onnx soundfile numpy
# models/kokoro-v1.0.onnx and models/voices-v1.0.bin from github.com/thewh1teagle/kokoro-onnx releases (model-files-v1.0)
.venv/Scripts/python record.py      # needs the Pukaar server running; resets the flood night
.venv/Scripts/python tts.py
.venv/Scripts/python mix.py
.venv/Scripts/python prepare.py
.venv/Scripts/python render.py
.venv/Scripts/python srt.py
```

Edit `narration.json` to change the words; scene timing follows the voice automatically.

The numbers in the film come from `docs/eval-report.md` (a simulated night in rules mode). Clock times in the phone mockups on the landing page are illustrative; everything in the screen recordings is the real app.
