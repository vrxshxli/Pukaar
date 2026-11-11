"""Render the composition to an MP4, frame by frame.

  .venv/Scripts/python render.py                  full film -> out/pukaar-demo.mp4
  .venv/Scripts/python render.py --stills 3,20,95 save PNG stills at those seconds (for checking)
  .venv/Scripts/python render.py --from 90 --to 130 --name rescue   render a section
"""
import argparse
import asyncio
import functools
import http.server
import subprocess
import threading
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.async_api import async_playwright

HERE = Path(__file__).parent
OUT = HERE / "out"
PORT = 8765
FPS = 30


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=str(HERE))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


async def main(args):
    OUT.mkdir(exist_ok=True)
    srv = serve()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"http://127.0.0.1:{PORT}/compose/index.html")
        await page.evaluate("window.ready")
        if errors:
            raise SystemExit("composition error: " + errors[0])
        total = await page.evaluate("window.TOTAL")
        stage = page.locator("#stage")

        if args.stills:
            for s in [float(x) for x in args.stills.split(",")]:
                await page.evaluate(f"window.seek({s})")
                await stage.screenshot(path=str(OUT / f"still_{s:06.1f}.png"))
                print("still", s)
            if errors:
                print("errors:", errors[:3])
            await browser.close()
            srv.shutdown()
            return

        start = args.start or 0.0
        end = min(args.end or total, total)
        name = args.name or "pukaar-demo"
        mp4 = OUT / f"{name}.mp4"
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y",
               "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
               "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(HERE / "build" / "mix.wav"),
               "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(mp4)]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        frames = int((end - start) * FPS)
        t0 = time.time()
        for i in range(frames):
            t = start + i / FPS
            await page.evaluate(f"window.seek({t:.4f})")
            ff.stdin.write(await stage.screenshot(type="jpeg", quality=93))
            if i % 300 == 0:
                el = time.time() - t0
                print(f"frame {i}/{frames}  t={t:6.1f}s  {el:5.0f}s elapsed  eta {el / max(i, 1) * (frames - i):5.0f}s", flush=True)
        ff.stdin.close()
        ff.wait()
        if errors:
            print("page errors:", errors[:3])
        print("wrote", mp4)
        await browser.close()
    srv.shutdown()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills")
    ap.add_argument("--from", dest="start", type=float)
    ap.add_argument("--to", dest="end", type=float)
    ap.add_argument("--name")
    asyncio.run(main(ap.parse_args()))
