"""Record the real Pukaar app for the demo video.

Drives the running server (http://localhost:8000) with headless Chromium and
records each browser page as a .webm. Several pages record at the same time,
so the control room and the phones can be shown side by side in sync.

Every tap is logged with its time (seconds from that page's first frame) and
position, so the composition can draw tap ripples and zoom to the right place.

Usage:  .venv/Scripts/python record.py            (needs the server running)
Output: recordings/<clip>/<page>.webm, recordings/events.json, recordings/snaps/*.png
"""
import asyncio
import json
import re
import shutil
import time
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
OUT = Path(__file__).parent / "recordings"
OFFICER = ("rao", "pukaar-officer")
CREW = ("boat1", "pukaar-volunteer")
DESK = {"width": 1600, "height": 900}
PHONE = {"width": 390, "height": 844}

KAMLA_VOICE = "पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे"
DAUGHTER = ("+91 90000 05101", "Please help my mother Kamla Devi, Lane 4 behind Hanuman temple, Shanti Nagar. Water rising!!")
NEIGHBOUR = ("+91 90000 05102", "shantinagar gali 4 mandir ke peeche budhi amma aur bachcha phase hai")
RUMOUR = "Powai dam has burst!! whole kurla will drown, forward to all"
GAS = "गली 7 मस्जिद के पास गैस की बदबू आ रही है और पानी अंदर है, क्या करें?"

events: list[dict] = []
pages: list[dict] = []  # each page's first-frame time on one shared clock


class Rec:
    """One recorded page plus its clock."""

    def __init__(self, clip, name, page):
        self.clip, self.name, self.page, self.t0 = clip, name, page, time.monotonic()
        pages.append({"clip": clip, "page": name, "t0": self.t0})

    def t(self):
        return round(time.monotonic() - self.t0, 2)

    def mark(self, label, box=None):
        e = {"clip": self.clip, "page": self.name, "t": self.t(), "label": label}
        if box:
            e |= {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2, "w": box["width"], "h": box["height"]}
        events.append(e)

    async def tap(self, locator, label):
        await locator.scroll_into_view_if_needed()
        box = await locator.bounding_box()
        self.mark(label, box)
        await asyncio.sleep(0.35)  # let the ripple lead the change
        await locator.click()


async def new_page(browser, clip, name, size, login=None, scale=1, mobile=False):
    ctx = await browser.new_context(viewport=size, device_scale_factor=scale, is_mobile=mobile, has_touch=mobile,
                                    record_video_dir=str(OUT / clip / name),
                                    record_video_size={"width": size["width"] * scale, "height": size["height"] * scale},
                                    locale="en-IN")
    if login:
        r = await ctx.request.post(f"{BASE}/api/auth/login", data={"username": login[0], "password": login[1]})
        assert r.ok, await r.text()
    page = await ctx.new_page()
    return ctx, Rec(clip, name, page)


async def api(ctx, path, body=None):
    r = await (ctx.request.post(f"{BASE}{path}", data=body) if body is not None else ctx.request.get(f"{BASE}{path}"))
    return await r.json()


async def finish(ctx, rec):
    await ctx.close()
    src = Path(await rec.page.video.path())
    dst = OUT / rec.clip / f"{rec.name}.webm"
    shutil.move(src, dst)
    shutil.rmtree(OUT / rec.clip / rec.name, ignore_errors=True)
    print("  saved", dst.relative_to(OUT.parent))


async def reset(browser):
    ctx = await browser.new_context()
    await ctx.request.post(f"{BASE}/api/auth/login", data={"username": OFFICER[0], "password": OFFICER[1]})
    await ctx.request.post(f"{BASE}/api/replay", data={"action": "reset"})
    await ctx.request.post(f"{BASE}/api/settings", data={"automation": True, "llm_mode": "rules"})
    await ctx.close()


async def pick_identity(rec, name):
    await rec.page.goto(f"{BASE}/chat")
    await rec.page.evaluate("localStorage.removeItem('pukaar-identity')")
    await rec.page.reload()
    await rec.tap(rec.page.get_by_role("button", name=re.compile(name)), f"I am {name}")


async def send_chat(rec, text, label):
    box = rec.page.get_by_label("Message")
    await box.click()
    await box.type(text, delay=28)
    await rec.tap(rec.page.get_by_role("button", name="Send"), label)


async def clip_landing(browser):
    print("landing")
    ctx, r = await new_page(browser, "landing", "desk", DESK)
    await r.page.goto(BASE)
    await asyncio.sleep(6)
    r.mark("hero")
    height = await r.page.evaluate("document.body.scrollHeight")
    y = 0
    while y < height - DESK["height"]:
        y += 5
        await r.page.evaluate(f"window.scrollTo(0, {y})")
        await asyncio.sleep(0.016)
    await asyncio.sleep(2)
    # Element snapshots for the agents scene.
    snaps = OUT / "snaps"
    snaps.mkdir(parents=True, exist_ok=True)
    await r.page.evaluate("window.scrollTo(0, 0)")
    cards = r.page.locator("#how ol > li")
    for i in range(await cards.count()):
        await cards.nth(i).screenshot(path=str(snaps / f"step{i + 1}.png"))
    await finish(ctx, r)


async def clip_login(browser):
    print("login")
    ctx, r = await new_page(browser, "login", "desk", DESK)
    await r.page.goto(f"{BASE}/login")
    await asyncio.sleep(1.2)
    await r.page.get_by_label("Username").type(OFFICER[0], delay=110)
    await r.page.get_by_label("Password").type(OFFICER[1], delay=70)
    await r.tap(r.page.get_by_role("button", name="Sign in"), "Sign in")
    await asyncio.sleep(4)
    await finish(ctx, r)


async def clip_rescue(browser):
    """Kamla's rescue: the control room, Kamla's phone and Boat 1's phone, recorded together."""
    print("rescue")
    await reset(browser)
    dctx, dash = await new_page(browser, "rescue", "dash", DESK, login=OFFICER)
    pctx, phone = await new_page(browser, "rescue", "phone", PHONE, mobile=True)
    vctx, crew = await new_page(browser, "rescue", "crew", PHONE, login=CREW, mobile=True)
    await dash.page.goto(f"{BASE}/control")
    await crew.page.goto(f"{BASE}/volunteer")
    await pick_identity(phone, "Kamla Devi")
    await asyncio.sleep(2)

    await send_chat(phone, KAMLA_VOICE, "Kamla sends a voice note")
    await asyncio.sleep(4)
    dash.mark("ticket appears")
    await api(dctx, "/api/messages", {"phone": DAUGHTER[0], "text": DAUGHTER[1]})
    dash.mark("daughter's message merged")
    await asyncio.sleep(4)
    await api(dctx, "/api/messages", {"phone": NEIGHBOUR[0], "text": NEIGHBOUR[1]})
    dash.mark("neighbour's message merged")
    await asyncio.sleep(4)

    q = dash.page.locator('section[aria-label="Ticket queue"] button', has_text="Kamla Devi household").first
    await dash.tap(q, "Open the ticket")
    await asyncio.sleep(3.5)
    await dash.tap(dash.page.get_by_role("tab", name=re.compile("Reports")), "Raw messages")
    await asyncio.sleep(3.5)
    await dash.tap(dash.page.get_by_role("tab", name="Details"), "Why P1")
    await asyncio.sleep(2)
    card = dash.page.locator("article", has_text="Kamla Devi").first
    await card.hover()
    dash.mark("route preview", await card.bounding_box())
    await asyncio.sleep(3)
    await dash.tap(card.get_by_role("button", name=re.compile("Approve")), "Approve Boat 1")
    await asyncio.sleep(4)

    await crew.page.reload()
    await asyncio.sleep(2)
    await crew.tap(crew.page.get_by_role("button", name="Accept"), "Crew accepts")
    await asyncio.sleep(5)
    thread = await api(pctx, f"/api/chat/{'+91 90000 00412'}")
    otp = next(re.search(r"\b(\d{4})\b", m["text"]).group(1) for m in reversed(thread)
               if m["direction"] == "out" and "OTP" in m["text"])
    phone.mark(f"OTP {otp} arrives")
    await asyncio.sleep(2)
    await crew.tap(crew.page.get_by_role("button", name="Reached"), "Boat reached")
    await asyncio.sleep(2.5)
    await crew.tap(crew.page.get_by_role("button", name="Enter family OTP"), "Enter OTP")
    await crew.page.get_by_label("Family OTP").type(otp, delay=160)
    await crew.tap(crew.page.get_by_role("button", name="Confirm"), "Family confirmed safe")
    await asyncio.sleep(6)
    for ctx, rec in ((dctx, dash), (pctx, phone), (vctx, crew)):
        await finish(ctx, rec)


async def clip_signals(browser):
    """Rumour to Verify, gas leak to Saathi, blocked road, family lookup, popup, kill switch."""
    print("signals")
    dctx, dash = await new_page(browser, "signals", "dash", DESK, login=OFFICER)
    pctx, phone = await new_page(browser, "signals", "phone", PHONE, mobile=True)
    vctx, crew = await new_page(browser, "signals", "crew", PHONE, login=CREW, mobile=True)
    await dash.page.goto(f"{BASE}/control")
    await crew.page.goto(f"{BASE}/volunteer")
    await pick_identity(phone, "Rukhsar Shaikh")
    await asyncio.sleep(1.5)

    await api(dctx, "/api/messages", {"phone": "+91 90000 05300", "text": RUMOUR})
    dash.mark("rumour arrives")
    await asyncio.sleep(2)
    await dash.tap(dash.page.get_by_role("tab", name=re.compile("Verify")), "Held in Verify")
    await asyncio.sleep(4)
    await dash.tap(dash.page.get_by_role("tab", name=re.compile("Active")), "Back to active")

    await send_chat(phone, GAS, "Gas leak question")
    await asyncio.sleep(6)
    phone.mark("Saathi replies with 1906")
    await asyncio.sleep(2)

    await crew.tap(crew.page.get_by_role("button", name="Lane blocked"), "Crew reports a blocked lane")
    await asyncio.sleep(1)
    await crew.tap(crew.page.get_by_role("button", name="Lane 6"), "Lane 6 blocked")
    await asyncio.sleep(1)
    dash.mark("map turns Lane 6 red")
    await asyncio.sleep(5)

    await dash.tap(dash.page.get_by_role("button", name="Chat", exact=True), "Chat opens as a card")
    await asyncio.sleep(4)
    await dash.tap(dash.page.get_by_role("button", name="Family", exact=True), "Family lookup card")
    await asyncio.sleep(3)
    await dash.tap(dash.page.get_by_role("button", name="Control", exact=True), "Back to control")
    await asyncio.sleep(1.5)

    await dash.tap(dash.page.get_by_role("switch"), "Automation off")
    await asyncio.sleep(3.5)
    await dash.tap(dash.page.get_by_role("switch"), "Automation on")
    await asyncio.sleep(2)
    for ctx, rec in ((dctx, dash), (pctx, phone), (vctx, crew)):
        await finish(ctx, rec)


async def clip_family(browser):
    print("family")
    ctx, r = await new_page(browser, "family", "phone", PHONE, mobile=True)
    await r.page.goto(f"{BASE}/family")
    await asyncio.sleep(1.5)
    await r.page.get_by_placeholder("for example Kamla").type("Pinto", delay=120)
    await r.page.get_by_placeholder("for example Lane 4").type("Lane 2", delay=120)
    await r.tap(r.page.get_by_role("button", name="Search"), "Search")
    await asyncio.sleep(5)
    await finish(ctx, r)


async def clip_replay(browser):
    """The whole night at 10x: the queue, map and approvals filling in real time."""
    print("replay")
    await reset(browser)
    dctx, dash = await new_page(browser, "replay", "dash", DESK, login=OFFICER)
    await dash.page.goto(f"{BASE}/control")
    await asyncio.sleep(2)
    await dash.tap(dash.page.get_by_role("button", name="10×"), "10× speed")
    await dash.tap(dash.page.get_by_role("button", name=re.compile("Start the replay")), "Start the flood night")
    await asyncio.sleep(38)
    await dash.page.get_by_role("button", name=re.compile("Pause the replay")).click()
    await asyncio.sleep(1)
    await finish(dctx, dash)


async def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for clip in (clip_landing, clip_login, clip_rescue, clip_signals, clip_family, clip_replay):
            await clip(browser)
        await reset(browser)
        await browser.close()
    (OUT / "events.json").write_text(json.dumps({"events": events, "pages": pages}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(events)} events")


if __name__ == "__main__":
    asyncio.run(main())
