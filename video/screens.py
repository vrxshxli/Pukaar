"""Capture README screenshots of the real app (http://localhost:8000).

Sets up a realistic state (Kamla's rescue mid-flow, then a busy replay) and saves
crisp PNGs to docs/screenshots/. Resets the flood night when it starts and when it ends.
Usage: .venv/Scripts/python screens.py
"""
import asyncio
import re
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
OUT = Path(__file__).parent.parent / "docs" / "screenshots"
DESK = {"width": 1600, "height": 900}
PHONE = {"width": 390, "height": 844}
OFFICER = {"username": "rao", "password": "pukaar-officer"}
CREW = {"username": "boat1", "password": "pukaar-volunteer"}
KAMLA = ("+91 90000 00412", "पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे")
DAUGHTER = ("+91 90000 05101", "Please help my mother Kamla Devi, Lane 4 behind Hanuman temple, Shanti Nagar. Water rising!!")
NEIGHBOUR = ("+91 90000 05102", "shantinagar gali 4 mandir ke peeche budhi amma aur bachcha phase hai")


async def ctx(browser, size, scale, login=None, dark=False, mobile=False):
    c = await browser.new_context(viewport=size, device_scale_factor=scale, is_mobile=mobile, has_touch=mobile, locale="en-IN")
    if dark:
        await c.add_init_script("localStorage.setItem('pukaar-theme', 'dark')")
    if login:
        assert (await c.request.post(f"{BASE}/api/auth/login", data=login)).ok
    return c


async def shot(page, name, **kw):
    await page.screenshot(path=str(OUT / f"{name}.png"), **kw)
    print("saved", name)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        admin = await ctx(b, DESK, 1, OFFICER)
        await admin.request.post(f"{BASE}/api/replay", data={"action": "reset"})

        # Landing page.
        c = await ctx(b, DESK, 2)
        pg = await c.new_page()
        await pg.goto(BASE)
        await asyncio.sleep(7)
        await shot(pg, "landing")
        await pg.evaluate("document.querySelector('header').style.display='none'")
        await pg.locator("#how").screenshot(path=str(OUT / "landing-how.png"))
        await pg.locator("#people").screenshot(path=str(OUT / "landing-people.png"))
        print("saved landing sections")
        await pg.goto(f"{BASE}/login")
        await asyncio.sleep(1.5)
        await shot(pg, "login")
        await c.close()

        # Kamla's three messages, then the dashboard with the approval waiting.
        for phone, text in (KAMLA, DAUGHTER, NEIGHBOUR):
            await admin.request.post(f"{BASE}/api/messages", data={"phone": phone, "text": text})
            await asyncio.sleep(0.6)
        d = await ctx(b, DESK, 2, OFFICER)
        dash = await d.new_page()
        await dash.goto(f"{BASE}/control")
        await asyncio.sleep(4)
        await dash.locator('section[aria-label="Ticket queue"] button', has_text="Kamla Devi household").first.click()
        await asyncio.sleep(2)
        await dash.locator("article", has_text="Kamla Devi").first.hover()
        await asyncio.sleep(1.5)
        await shot(dash, "dashboard")
        await dash.get_by_role("tab", name=re.compile("Reports")).click()
        await asyncio.sleep(1)
        await dash.locator('aside[aria-label^="Ticket"]').screenshot(path=str(OUT / "ticket-detail.png"))
        print("saved ticket-detail")
        await dash.get_by_role("tab", name="Details").click()
        await dash.locator("article", has_text="Kamla Devi").first.screenshot(path=str(OUT / "approval-card.png"))
        print("saved approval-card")

        # Approve, crew accepts: phones show the real-time updates.
        await dash.locator("article", has_text="Kamla Devi").first.get_by_role("button", name=re.compile("Approve")).click()
        await asyncio.sleep(2)
        v = await ctx(b, PHONE, 3, CREW, mobile=True)
        crew = await v.new_page()
        await crew.goto(f"{BASE}/volunteer")
        await asyncio.sleep(3)
        await crew.get_by_role("button", name="Accept").click()
        await asyncio.sleep(3)
        await shot(crew, "volunteer")
        await v.close()

        k = await ctx(b, PHONE, 3, mobile=True)
        await k.add_init_script("localStorage.setItem('pukaar-identity', JSON.stringify({name: 'Kamla Devi', area: 'Lane 4, Shanti Nagar', phone: '+91 90000 00412'}))")
        kp = await k.new_page()
        await kp.goto(f"{BASE}/chat")
        await asyncio.sleep(3)
        await shot(kp, "chat-kamla")
        await k.close()

        f = await ctx(b, PHONE, 3, mobile=True)
        fp = await f.new_page()
        await fp.goto(f"{BASE}/family")
        await fp.get_by_placeholder("for example Kamla").fill("Pinto")
        await fp.get_by_placeholder("for example Lane 4").fill("Lane 2")
        await fp.get_by_role("button", name="Search").click()
        await asyncio.sleep(2)
        await shot(fp, "family")
        await f.close()

        # Chat opened as a card inside the control room.
        await dash.get_by_role("button", name="Chat", exact=True).click()
        await asyncio.sleep(3)
        await shot(dash, "dashboard-popup")
        await dash.get_by_role("button", name="Control", exact=True).click()
        await d.close()

        # A busy night: replay at 10x for a while.
        await admin.request.post(f"{BASE}/api/replay", data={"action": "reset"})
        await admin.request.post(f"{BASE}/api/replay", data={"action": "start", "speed": 10})
        await asyncio.sleep(150)
        await admin.request.post(f"{BASE}/api/replay", data={"action": "pause"})
        d = await ctx(b, DESK, 2, OFFICER)
        dash = await d.new_page()
        await dash.goto(f"{BASE}/control")
        await asyncio.sleep(4)
        await shot(dash, "dashboard-night")
        await d.close()
        dd = await ctx(b, DESK, 2, OFFICER, dark=True)
        dark = await dd.new_page()
        await dark.goto(f"{BASE}/control")
        await asyncio.sleep(4)
        await shot(dark, "dashboard-dark")
        await dd.close()

        await admin.request.post(f"{BASE}/api/replay", data={"action": "reset"})
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
