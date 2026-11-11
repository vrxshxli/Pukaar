"""Full-page phone screenshots of every screen, for checking the mobile layout.
Usage: .venv/Scripts/python mobile_shots.py [outdir]"""
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "mobile")
PHONE = {"width": 390, "height": 844}


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)

        async def ctx(login=None):
            c = await b.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True, locale="en-IN")
            if login:
                await c.request.post(f"{BASE}/api/auth/login", data={"username": login[0], "password": login[1]})
            return c

        admin = await ctx(("rao", "pukaar-officer"))
        await admin.request.post(f"{BASE}/api/replay", data={"action": "reset"})
        for phone, text in [("+91 90000 00412", "पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे"),
                            ("+91 90000 05101", "Please help my mother Kamla Devi, Lane 4 behind Hanuman temple, Shanti Nagar. Water rising!!")]:
            await admin.request.post(f"{BASE}/api/messages", data={"phone": phone, "text": text})

        c = await ctx()
        pg = await c.new_page()
        for path, name, wait in [("/", "landing", 6), ("/login", "login", 1.5), ("/family", "family", 1.5)]:
            await pg.goto(BASE + path)
            await asyncio.sleep(wait)
            await pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            await pg.screenshot(path=str(OUT / f"{name}-top.png"))
            print(name)
        await pg.goto(BASE + "/chat")
        await pg.evaluate("localStorage.removeItem('pukaar-identity')")
        await pg.reload()
        await asyncio.sleep(1.5)
        await pg.screenshot(path=str(OUT / "chat-pick.png"), full_page=True)
        await pg.get_by_role("button", name=re.compile("Kamla Devi")).click()
        await asyncio.sleep(2)
        await pg.screenshot(path=str(OUT / "chat.png"))
        print("chat")
        await c.close()

        d = await ctx(("rao", "pukaar-officer"))
        dp = await d.new_page()
        await dp.goto(BASE + "/control")
        await asyncio.sleep(4)
        await dp.screenshot(path=str(OUT / "control-top.png"))
        await dp.screenshot(path=str(OUT / "control.png"), full_page=True)
        for k, y in enumerate((760, 1400, 2100), 2):
            await dp.evaluate(f"document.querySelector('#root .overflow-y-auto').scrollTo(0, {y})")
            await asyncio.sleep(0.8)
            await dp.screenshot(path=str(OUT / f"control-{k}.png"))
        print("control")
        await d.close()

        v = await ctx(("boat1", "pukaar-volunteer"))
        vp = await v.new_page()
        await vp.goto(BASE + "/volunteer")
        await asyncio.sleep(3)
        await vp.screenshot(path=str(OUT / "volunteer.png"), full_page=True)
        print("volunteer")
        await v.close()
        await admin.request.post(f"{BASE}/api/replay", data={"action": "reset"})
        await b.close()


asyncio.run(main())
