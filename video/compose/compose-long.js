/* Pukaar film. Every frame is a pure function of time t (seconds), so the
   renderer can seek to any frame and screenshot it. Recordings are shown as
   numbered JPEG frames of the real app. */
'use strict'
const D = window.DATA
const W = 1920, H = 1080
const TOTAL = D.timeline.total
const LINES = D.timeline.lines

// ---------- helpers ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x))
const prog = (t, a, b) => clamp((t - a) / (b - a))
const lerp = (a, b, p) => a + (b - a) * p
const E = {
  out: (p) => 1 - Math.pow(1 - p, 3),
  in: (p) => p * p * p,
  io: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
  back: (p) => { const c = 1.9; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2) },
  elastic: (p) => (p === 0 ? 0 : p === 1 ? 1 : Math.pow(2, -10 * p) * Math.sin((p * 10 - 0.75) * (2 * Math.PI) / 3) + 1),
}
const rand = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x) }
function h(tag, cls, html, parent) {
  const el = document.createElement(tag)
  if (cls) el.className = cls
  if (html != null) el.innerHTML = html
  if (parent) parent.appendChild(el)
  return el
}
function css(el, o) { for (const k in o) el.style[k] = o[k] }
function show(el, p, { y = 40, x = 0, s = 1, r = 0, blur = 0 } = {}) {
  const q = clamp(p)
  el.style.opacity = q
  el.style.transform = `translate(${(1 - q) * x}px, ${(1 - q) * y}px) scale(${lerp(s, 1, q)}) rotate(${(1 - q) * r}deg)`
  el.style.filter = blur ? `blur(${(1 - q) * blur}px)` : ''
}
const esc = (s) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c])
function words(el, text, cls = '') {
  el.innerHTML = text.split(' ').map((w) => `<span class="word ${cls}">${esc(w)}</span>`).join(' ')
  return [...el.querySelectorAll('.word')]
}
function staggerWords(ws, p, { y = 60, r = 8, spread = 0.6, s = 0.6 } = {}) {
  const n = ws.length
  ws.forEach((w, i) => {
    const q = E.back(clamp((p - (i / Math.max(n, 1)) * spread) / (1 - spread)))
    w.style.opacity = clamp(q * 1.4)
    w.style.transform = `translateY(${(1 - q) * y}px) rotate(${(1 - q) * r}deg) scale(${lerp(s, 1, clamp(q))})`
  })
}

// ---------- icons (same line style as the app) ----------
const ICON = {
  chat: '<path d="M4 5h16v11H9l-5 4z"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  boat: '<path d="M3 15h18l-2.5 4h-13z"/><path d="M12 4v11M12 5l5 7h-5"/>',
  shield: '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.2 7.5 9.5 4.3-1.3 7.5-4.9 7.5-9.5V6z"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.4 4.3 4.3 0 0 1 19.5 10c0 5.4-7.5 10-7.5 10z"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  phone: '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  cloudx: '<path d="M7 18a4 4 0 0 1 .5-8 5.5 5.5 0 0 1 10.4 1.6A3.5 3.5 0 0 1 17.5 18z"/><path d="M3 3l18 18"/>',
  laptop: '<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M2 19h20"/>',
  wind: '<path d="M3 8h11a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h7"/>',
  quake: '<path d="M2 12h4l2-6 3 12 3-9 2 3h6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  flame: '<path d="M12 21c-4 0-7-2.8-7-6.5 0-3.5 3-5.5 4-9 1.5 1.5 2 3 2 4.5 1-1 1.8-2.5 2-4.5 2.5 2 5 5.5 5 9 0 3.7-3 6.5-6 6.5z"/>',
  water: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
}
const icon = (n, size = 40, sw = 1.8, color = 'currentColor') =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${ICON[n]}</svg>`
const LOGO = (size, fill = '#2F5D58', ink = '#fff') => `<svg width="${size}" height="${size}" viewBox="0 0 40 40"><rect x="1" y="1" width="38" height="38" rx="12" fill="${fill}"/><path d="M13 15a9 9 0 0 1 14 0" stroke="${ink}" stroke-width="2.6" fill="none" stroke-linecap="round"/><path d="M16.5 18.5a4.5 4.5 0 0 1 7 0" stroke="${ink}" stroke-width="2.6" fill="none" stroke-linecap="round"/><circle cx="20" cy="22" r="1.9" fill="${ink}"/><path d="M8 28c3-2.4 5-2.4 8 0s5 2.4 8 0 5-2.4 8 0" stroke="${ink}" stroke-width="2.4" fill="none" stroke-linecap="round"/></svg>`

// ---------- recordings ----------
const pending = []
function framePath(clip, page, sec) {
  const info = D.clips[clip][page]
  const n = clamp(Math.floor(sec * D.fps) + 1, 1, info.frames)
  return `../build/frames/${clip}/${page}/${String(n).padStart(6, '0')}.jpg`
}
function setImg(img, src) {
  if (img.dataset.src === src) return
  img.dataset.src = src
  img.src = src
  pending.push(img.decode().catch(() => {}))
}
function ev(clip, label) {
  const e = D.events.find((x) => x.clip === clip && x.label.startsWith(label))
  if (!e) throw new Error(`no event ${clip}/${label}`)
  return { ...e, c: e.t + D.clips[clip][e.page].offset }
}

// A device that plays one page of a recording, with a zooming camera and tap ripples.
function Device(parent, kind, clip, page, { x, y, scale, label }) {
  const info = D.clips[clip][page]
  const root = h('div', kind, null, parent)
  const sw = info.w * scale, sh = info.h * scale
  let screen
  if (kind === 'laptop') {
    const bez = h('div', 'bezel', null, root)
    screen = h('div', 'screen', null, bez)
    h('div', 'base', null, root)
  } else {
    const body = h('div', 'body', null, root)
    const status = h('div', 'status', '<span>9:47</span><span class="notch"></span><span>●●● ▮</span>', body)
    css(status, { width: sw + 'px' })
    screen = h('div', 'screen', null, body)
  }
  css(screen, { width: sw + 'px', height: sh + 'px' })
  const zoomer = h('div', 'zoomer', null, screen)
  const img = h('img', '', null, zoomer)
  css(img, { width: info.w + 'px', height: info.h + 'px' })
  if (label) h('div', 'dev-label', label, root)
  const fx = h('div', 'abs', null, screen)
  css(fx, { inset: '0' })
  css(root, { left: x + 'px', top: y + 'px' })
  const taps = D.events.filter((e) => e.clip === clip && e.page === page && e.x != null)
  const dot = h('div', 'tap-dot', null, fx), ring = h('div', 'ripple', null, fx), tag = h('div', 'tap-label', '', fx)
  return {
    root, scale, info,
    // c: clip clock (seconds). cam: {z, fx, fy} zoom and focus point in page pixels.
    set(c, cam = { z: 1 }) {
      const pt = c - info.offset
      setImg(img, framePath(clip, page, pt))
      const z = cam.z || 1
      const fx0 = cam.fx ?? info.w / 2, fy0 = cam.fy ?? info.h / 2
      // Keep the focus point centred, without showing past the page edges.
      const vw = info.w / z, vh = info.h / z
      const ox = clamp(fx0 - vw / 2, 0, info.w - vw), oy = clamp(fy0 - vh / 2, 0, info.h - vh)
      zoomer.style.transform = `scale(${scale * z}) translate(${-ox}px, ${-oy}px)`
      // The latest tap within the last 1.4 s.
      const tap = taps.filter((e) => pt >= e.t - 0.35 && pt <= e.t + 1.4).pop()
      if (tap) {
        const k = scale * z, px = (tap.x - ox) * k, py = (tap.y - oy) * k
        const q = prog(pt, tap.t - 0.35, tap.t + 0.6)
        css(dot, { left: px + 'px', top: py + 'px', opacity: 1 - prog(pt, tap.t + 0.6, tap.t + 1.2), transform: `scale(${1 + 0.4 * Math.sin(q * Math.PI)})` })
        const rr = 20 + 90 * E.out(q)
        css(ring, { left: px - rr + 'px', top: py - rr + 'px', width: rr * 2 + 'px', height: rr * 2 + 'px', opacity: 1 - q })
        tag.textContent = tap.label
        const tq = E.back(prog(pt, tap.t - 0.3, tap.t + 0.1)) * (1 - prog(pt, tap.t + 1.1, tap.t + 1.4))
        const sw2 = parseFloat(screen.style.width)
        const left = px + 24 + 260 > sw2 ? px - 24 - 260 : px + 24
        css(tag, { left: clamp(left, 8, sw2 - 270) + 'px', top: py - 60 + 'px', opacity: tq, transform: `scale(${lerp(0.6, 1, tq)})` })
      } else {
        dot.style.opacity = ring.style.opacity = tag.style.opacity = 0
      }
    },
  }
}

// Smoothly interpolated camera keys: [[t, z, fx, fy], ...]
function camAt(keys, t) {
  if (t <= keys[0][0]) return { z: keys[0][1], fx: keys[0][2], fy: keys[0][3] }
  for (let i = 1; i < keys.length; i++) {
    if (t <= keys[i][0]) {
      const a = keys[i - 1], b = keys[i], p = E.io(prog(t, a[0], b[0]))
      return { z: lerp(a[1], b[1], p), fx: lerp(a[2], b[2], p), fy: lerp(a[3], b[3], p) }
    }
  }
  const k = keys[keys.length - 1]
  return { z: k[1], fx: k[2], fy: k[3] }
}

// ---------- scene timing from the voiceover ----------
const ORDER = ['cold', 'problem', 'title', 'agents', 'login', 'rescue', 'signals', 'family', 'replay', 'safety', 'tech', 'results', 'beyond', 'outro']
const CHAPTER = { problem: ['01', 'The problem'], agents: ['02', 'Meet the agents'], login: ['03', 'Live: the real app'], rescue: ['03', 'Live: one rescue'],
  signals: ['03', 'Live: hard cases'], family: ['03', 'Live: family lookup'], replay: ['03', 'Live: a whole night'], safety: ['04', 'Safety'],
  tech: ['05', 'Under the hood'], results: ['06', 'Results'], beyond: ['07', 'Beyond floods'] }
const SC = {}
ORDER.forEach((id, i) => {
  const ls = LINES.filter((l) => l.scene === id)
  SC[id] = { id, lines: ls, start: i === 0 ? 0 : ls[0].start - 0.45 }
})
ORDER.forEach((id, i) => { SC[id].end = i < ORDER.length - 1 ? SC[ORDER[i + 1]].start : TOTAL })
// Line windows in scene-local time: [start, nextStart).
function L(sc, i) {
  const l = sc.lines[i], nx = sc.lines[i + 1]
  return { a: l.start - sc.start, e: l.end - sc.start, b: (nx ? nx.start : sc.end) - sc.start }
}

const scenesEl = document.getElementById('scenes')
const builders = {}

// ---------- 1. Cold open: night, rain, every phone calling ----------
builders.cold = (root, sc) => {
  const sky = h('div', 'abs', null, root)
  css(sky, { inset: 0, background: 'radial-gradient(1200px 700px at 50% 20%, #1d3a35, #0b1916 70%)' })
  const water = h('div', 'abs', '<svg width="1920" height="600" viewBox="0 0 1920 600" preserveAspectRatio="none"><path id="wv1" fill="#2a5a52" opacity=".55"/><path id="wv2" fill="#3c7a6f" opacity=".45"/></svg>', root)
  css(water, { left: 0, right: 0, bottom: 0, height: '600px' })
  const wv1 = water.querySelector('#wv1'), wv2 = water.querySelector('#wv2')
  const bubbles = D.messages.slice(0, 26).map((m, i) => {
    const b = h('div', 'bubble', `<small>${icon('phone', 13, 2, '#5d716c')} ${String(Math.floor(9 + rand(i) * 80)).padStart(2, '0')} new message</small>${esc(m)}`, root)
    b._x = 80 + rand(i + 3) * 1500; b._y = 120 + rand(i + 9) * 620; b._t = 0.6 + i * 0.42
    return b
  })
  const count = h('div', 'abs caps', '', root)
  css(count, { right: '70px', top: '60px', color: '#cfe3dc', fontSize: '20px', textAlign: 'right' })
  const big = h('div', 'center serif', '', root)
  css(big, { color: '#fff', fontSize: '140px', fontWeight: 600, textAlign: 'center', whiteSpace: 'nowrap', textShadow: '0 10px 40px rgba(0,0,0,.5)' })
  big.innerHTML = '<div class="t1">10:00 PM</div><div class="t2 caps" style="font-family:var(--sans);font-size:30px;color:#f0b3a6;letter-spacing:.3em;margin-top:6px">Shanti Nagar · Mumbai</div>'
  const line2 = h('div', 'center serif', '', root)
  css(line2, { color: '#fff', fontSize: '76px', fontWeight: 500, width: '1500px', textAlign: 'center', textShadow: '0 10px 40px rgba(0,0,0,.6)' })
  const ws2 = words(line2, 'Every phone in the ward is calling for help.')
  const kam = h('div', 'center', '', root)
  kam.innerHTML = `<div style="display:flex;align-items:center;gap:28px;background:#fbfcfb;border-radius:30px 30px 30px 8px;padding:28px 36px;box-shadow:0 30px 80px rgba(0,0,0,.5);width:1180px">
    <div style="flex:none;width:84px;height:84px;border-radius:50%;background:#d4705f;display:flex;align-items:center;justify-content:center;color:#fff">${icon('chat', 44, 2, '#fff')}</div>
    <div><div class="caps" style="font-size:16px;color:#4f8a4c">🎤 Voice note · Hindi · Kamla Devi, 68 · Lane 4</div>
    <div style="font-size:40px;line-height:1.35;margin-top:8px;color:#1f3d39">${esc(D.timeline.lines[2].caption ? 'पानी घुटनों तक आ गया है, पोते को बुखार है… गली चार, हनुमान मंदिर के पीछे' : '')}</div>
    <div class="wave" style="display:flex;gap:5px;align-items:center;height:46px;margin-top:12px"></div></div></div>`
  const wave = kam.querySelector('.wave')
  const bars = Array.from({ length: 56 }, () => h('i', '', null, wave))
  bars.forEach((b) => css(b, { width: '7px', borderRadius: '4px', background: '#2f5d58', display: 'block' }))
  return (t) => {
    const l0 = L(sc, 0), l1 = L(sc, 1), l2 = L(sc, 2)
    const lvl = E.io(prog(t, 0, sc.end - sc.start))
    const amp = 18, base = 600 - 120 - lvl * 230
    const path = (ph, off) => {
      let d = `M0 600 L0 ${base + off}`
      for (let x = 0; x <= 1920; x += 40) d += ` L${x} ${base + off + Math.sin(x / 140 + t * 1.6 + ph) * amp + Math.sin(x / 57 + t * 2.3) * 6}`
      return d + ' L1920 600 Z'
    }
    wv1.setAttribute('d', path(0, 0)); wv2.setAttribute('d', path(2, 26))
    const n = Math.round(311 * E.in(prog(t, 0.5, sc.end - sc.start - 0.5)))
    count.innerHTML = `<div style="font-family:var(--serif);font-size:84px;letter-spacing:0;color:#fff;line-height:1">${n}</div>messages tonight`
    bubbles.forEach((b, i) => {
      const q = E.back(prog(t, b._t, b._t + 0.5))
      const fade = 1 - 0.75 * prog(t, l1.e - 0.5, l2.a + 0.3)
      css(b, { left: b._x + 'px', top: b._y - (t - b._t) * 6 + 'px', opacity: clamp(q) * fade * (t > l0.b ? 0.55 : 0.92), transform: `scale(${lerp(0.4, 1, clamp(q))}) rotate(${(rand(i) - 0.5) * 6}deg)`, filter: t > l1.b - 0.3 ? `blur(${3 * prog(t, l1.b - 0.3, l2.a + 0.4)}px)` : '' })
    })
    const p0 = E.out(prog(t, l0.a - 0.3, l0.a + 0.6)) * (1 - prog(t, l0.b - 0.4, l0.b))
    big.style.opacity = p0
    big.style.transform = `translate(-50%, -50%) scale(${lerp(1.25, 1, E.out(prog(t, l0.a - 0.3, l0.b)))})`
    big.querySelector('.t1').style.letterSpacing = lerp(0.3, 0.02, E.out(prog(t, 0, l0.b))) + 'em'
    const p1 = 1 - prog(t, l1.b - 0.35, l1.b)
    staggerWords(ws2, prog(t, l1.a - 0.2, l1.a + 1.6))
    line2.style.opacity = p1
    const pk = E.back(prog(t, l2.a - 0.3, l2.a + 0.5))
    kam.style.opacity = clamp(pk)
    kam.style.transform = `translate(-50%, -50%) scale(${lerp(0.7, 1, clamp(pk))}) rotate(${(1 - clamp(pk)) * -4}deg)`
    bars.forEach((b, i) => { const v = t > l2.a && t < l2.e ? 0.25 + Math.abs(Math.sin(i * 0.7 + t * 9) * Math.sin(i * 0.23 + t * 3.1)) : 0.15; b.style.height = 6 + v * 40 + 'px' })
  }
}

// ---------- 2. The problem, in two sentences ----------
builders.problem = (root, sc) => {
  const head = h('div', 'abs serif', '', root)
  css(head, { left: '50%', top: '50%', fontSize: '110px', fontWeight: 600, whiteSpace: 'nowrap' })
  const hw = words(head, 'The problem, in two sentences.')
  hw[1].style.color = 'var(--coral)'
  const s1 = h('div', 'abs', '', root)
  css(s1, { left: '120px', top: '300px', width: '1680px' })
  s1.innerHTML = '<div class="caps" style="color:var(--coral);font-size:18px">Sentence one</div><div class="serif q" style="font-size:44px;line-height:1.25;margin-top:10px">Hundreds of messages at once.</div>'
  const cards = [
    { t: 'The same family, three times', b: ['Help Kamla Devi, Lane 4!!', 'gali 4 mandir ke peeche amma phasi hai', 'पानी घुटनों तक… गली चार'], c: 'var(--teal)' },
    { t: 'Rumours', b: ['Powai dam has burst!! whole kurla will drown, forward to all'], c: 'var(--brick)' },
    { t: 'Three languages', b: ['हिंदी', 'मराठी', 'English'], c: 'var(--slate)', chips: true },
  ].map((c, i) => {
    const el = h('div', 'abs card', '', root)
    css(el, { left: 120 + i * 570 + 'px', top: '460px', width: '530px', height: '360px', padding: '30px' })
    el.innerHTML = `<div class="caps" style="font-size:17px;color:${c.c}">${c.t}</div>` + (c.chips
      ? `<div style="display:flex;flex-wrap:wrap;gap:14px;margin-top:40px">${c.b.map((x) => `<span class="chip" style="font-size:40px;padding:14px 26px;background:rgba(91,127,166,.14);color:#3f6283">${x}</span>`).join('')}</div>`
      : c.b.map((x, j) => `<div style="margin-top:${j ? 12 : 26}px;background:#fff;border:1px solid rgba(31,61,57,.14);border-radius:14px 14px 14px 4px;padding:12px 16px;font-size:22px;line-height:1.3;transform:translateX(${j * 18}px)">${esc(x)}</div>`).join(''))
    if (i === 1) h('div', 'abs serif', '?', el).style.cssText = 'right:26px;bottom:6px;font-size:150px;color:rgba(200,68,60,.25);font-weight:700'
    return el
  })
  const s2 = h('div', 'abs', '', root)
  css(s2, { left: '120px', top: '300px', width: '1680px' })
  s2.innerHTML = '<div class="caps" style="color:var(--coral);font-size:18px">Sentence two</div><div class="serif" style="font-size:44px;line-height:1.25;margin-top:10px">Boats go in the order calls arrive.</div>'
  const belt = h('div', 'abs', '', root)
  css(belt, { left: '0', top: '500px', width: '1920px', height: '300px' })
  const boat = h('div', 'abs', `<div style="width:170px;height:170px;border-radius:50%;background:var(--ink);display:flex;align-items:center;justify-content:center">${icon('boat', 90, 1.8, '#fff')}</div><div class="caps" style="text-align:center;margin-top:12px;font-size:16px;color:var(--muted)">Next boat</div>`, belt)
  css(boat, { left: '1620px', top: '40px' })
  const qs = ['Supplies · Lane 2', 'Repeat · Lane 9', 'Question · camp?', 'Rumour · dam', 'Repeat · Lane 4', 'Supplies · Lane 7', 'Question · water?', 'Repeat · Lane 2']
  const items = qs.map((q, i) => { const e = h('div', 'abs chip', esc(q), belt); css(e, { top: '95px', background: '#fff', border: '1px solid rgba(31,61,57,.18)', color: 'var(--ink)' }); return e })
  const p1 = h('div', 'abs chip', `${icon('heart', 26, 2.2)} P1 · Kamla Devi, fever · waiting`, belt)
  css(p1, { top: '92px', background: 'var(--brick)', color: '#fff', fontSize: '24px', boxShadow: '0 0 0 8px rgba(200,68,60,.18)' })
  const big = h('div', 'center', '', root)
  css(big, { textAlign: 'center' })
  big.innerHTML = '<div class="serif" style="font-size:300px;font-weight:700;color:var(--brick);line-height:1">463<span style="font-size:110px"> min</span></div><div style="font-size:34px;color:var(--muted);margin-top:10px">median wait for the most urgent families, first come, first served</div>'
  return (t) => {
    const l3 = L(sc, 0), l4 = L(sc, 1), l5 = L(sc, 2), l6 = L(sc, 3)
    const hp = prog(t, l3.a - 0.2, l3.a + 1.4)
    staggerWords(hw, hp, { y: -120, r: -12, spread: 0.5 })
    const shrink = E.io(prog(t, l3.b - 0.4, l3.b + 0.2))
    head.style.transform = `translate(${lerp(-50, -50, shrink)}%, -50%) translate(${shrink * -480}px, ${shrink * -330}px) scale(${lerp(1, 0.42, shrink)})`
    head.style.opacity = 1 - prog(t, l6.a - 0.3, l6.a)
    show(s1, prog(t, l4.a - 0.2, l4.a + 0.5), { x: -80, y: 0 })
    s1.style.opacity = clamp(prog(t, l4.a - 0.2, l4.a + 0.5)) * (1 - prog(t, l4.b - 0.3, l4.b))
    cards.forEach((c, i) => {
      const a = l4.a + (l4.e - l4.a) * (0.18 + i * 0.27)
      const q = E.back(prog(t, a - 0.2, a + 0.5)), out = prog(t, l4.b - 0.35, l4.b)
      c.style.opacity = clamp(q) * (1 - out)
      const jit = i === 1 && t > a && t < l4.b ? Math.sin(t * 50) * 3 : 0
      c.style.transform = `translate(${jit}px, ${(1 - clamp(q)) * 160 + out * -60}px) rotate(${(1 - clamp(q)) * (i - 1) * 14}deg) scale(${lerp(0.7, 1, clamp(q))})`
    })
    s2.style.opacity = clamp(prog(t, l5.a - 0.2, l5.a + 0.4)) * (1 - prog(t, l5.b - 0.3, l5.b))
    const bp = prog(t, l5.a, l5.b)
    belt.style.opacity = clamp(prog(t, l5.a - 0.2, l5.a + 0.4)) * (1 - prog(t, l5.b - 0.3, l5.b))
    const speed = 340
    items.forEach((e, i) => {
      const x = 1450 - i * 230 + bp * speed * (l5.b - l5.a) * 0.9
      css(e, { left: x + 'px', opacity: x > 1560 ? 1 - prog(x, 1560, 1640) : 1 })
    })
    const px = 1450 - items.length * 230 + bp * speed * (l5.b - l5.a) * 0.9
    css(p1, { left: Math.min(px, 1100) - 120 + 'px', transform: `scale(${1 + 0.04 * Math.sin(t * 8)})` })
    const q6 = E.elastic(prog(t, l6.a + 0.35, l6.a + 1.35))
    const shake = t > l6.a + 0.35 && t < l6.a + 0.95 ? (rand(Math.floor(t * 60)) - 0.5) * 30 : 0
    big.style.opacity = clamp(prog(t, l6.a + 0.25, l6.a + 0.5))
    big.style.transform = `translate(calc(-50% + ${shake}px), calc(-50% + ${shake * 0.6}px)) scale(${lerp(2.4, 1, clamp(q6))})`
  }
}

// ---------- 3. Title ----------
builders.title = (root, sc) => {
  const rings = Array.from({ length: 4 }, () => { const r = h('div', 'abs', null, root); css(r, { borderRadius: '50%', border: '3px solid var(--coral)' }); return r })
  const logo = h('div', 'center', LOGO(220), root)
  const name = h('div', 'abs serif', '', root)
  css(name, { left: '50%', top: '640px', transform: 'translateX(-50%)', fontSize: '150px', fontWeight: 600, whiteSpace: 'nowrap' })
  const letters = 'Pukaar'.split('').map((ch) => `<span class="word">${ch}</span>`).join('')
  name.innerHTML = letters + '<span class="word" style="color:var(--coral)">·</span> <span class="word" style="color:var(--muted);font-weight:400;font-size:90px">पुकार</span>'
  const ls = [...name.querySelectorAll('.word')]
  const tag = h('div', 'abs', 'Every call heard. Every family reached.', root)
  css(tag, { left: '50%', top: '850px', transform: 'translateX(-50%)', fontSize: '40px', color: 'var(--teal)', whiteSpace: 'nowrap' })
  const team = h('div', 'abs caps', '<span>Built by</span> <b style="color:var(--coral);font-size:46px;letter-spacing:.3em">Team Seekers</b>', root)
  css(team, { left: '50%', top: '120px', transform: 'translateX(-50%)', fontSize: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', textAlign: 'center' })
  return (t) => {
    const l7 = L(sc, 0), l8 = L(sc, 1)
    const lp = E.elastic(prog(t, 0, 1.2))
    const lift = E.io(prog(t, 1.0, 1.8))
    logo.style.transform = `translate(-50%, calc(-50% - ${lift * 170}px)) scale(${lerp(0, 1, lp) * lerp(1, 0.7, lift)}) rotate(${(1 - clamp(lp)) * -90}deg)`
    rings.forEach((r, i) => {
      const q = ((t - 0.3 - i * 0.5) % 2 + 2) % 2 / 2, size = 200 + q * 1200
      css(r, { left: 960 - size / 2 + 'px', top: 540 - 170 * lift - size / 2 + 'px', width: size + 'px', height: size + 'px', opacity: t > 0.3 + i * 0.5 ? (1 - q) * 0.6 : 0 })
    })
    ls.forEach((w, i) => {
      const q = E.back(prog(t, 1.2 + i * 0.07, 1.7 + i * 0.07))
      w.style.opacity = clamp(q); w.style.transform = `translateY(${(1 - clamp(q)) * 120}px) rotate(${(1 - clamp(q)) * 20}deg)`
    })
    show(tag, E.out(prog(t, l7.a + 2.0, l7.a + 2.8)), { y: 30 })
    tag.style.transform += ' translateX(-50%)'
    tag.style.left = '50%'
    const tq = E.out(prog(t, l8.a - 0.2, l8.a + 0.6))
    team.style.opacity = tq
    team.querySelector('b').style.letterSpacing = lerp(0.9, 0.3, tq) + 'em'
  }
}

// ---------- 4. Meet the agents ----------
const AGENTS = [
  { n: 'Listen', i: 'chat', one: 'Reads every message. Even voice notes, in Hindi.', snap: 1 },
  { n: 'Triage', i: 'layers', one: 'Merges repeats. Ranks by need. Writes down why.', snap: 2 },
  { n: 'Dispatch', i: 'boat', one: 'Nearest boat with a medic. A route around flooded lanes.', snap: 0 },
  { n: 'Officer', i: 'shield', one: 'A person decides. One tap.', snap: 3, human: true },
  { n: 'Loop', i: 'bell', one: 'Tells the family, in their own language, with a code.', snap: 4 },
]
builders.agents = (root, sc) => {
  const head = h('div', 'abs serif', 'Seven small helpers. <span style="color:var(--coral)">One job each.</span>', root)
  css(head, { left: '120px', top: '120px', fontSize: '58px', fontWeight: 600 })
  const track = h('div', 'abs', '<svg width="1680" height="40"><line x1="0" y1="20" x2="1680" y2="20" stroke="#2f5d58" stroke-opacity=".25" stroke-width="4" stroke-dasharray="10 10"/></svg>', root)
  css(track, { left: '120px', top: '290px' })
  const pulse = h('div', 'abs', null, root)
  css(pulse, { width: '26px', height: '26px', borderRadius: '50%', background: 'var(--coral)', boxShadow: '0 0 0 10px rgba(212,112,95,.25)', top: '297px' })
  const nodes = AGENTS.map((a, i) => {
    const el = h('div', 'abs', `<div class="disc" style="width:118px;height:118px;border-radius:${a.human ? '30px' : '50%'};background:${a.human ? 'var(--coral)' : 'var(--ink)'};color:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 18px 40px rgba(20,33,31,.25)">${icon(a.i, 56, 1.7, '#fff')}</div><div class="serif" style="text-align:center;font-size:28px;font-weight:600;margin-top:12px">${a.n}</div>`, root)
    el._x = 120 + i * 395 - 59 + (i === 0 ? 59 : i === 4 ? -59 : 0)
    return el
  })
  const panel = h('div', 'abs card', '', root)
  css(panel, { left: '120px', top: '500px', width: '1680px', height: '420px', padding: '44px 56px', display: 'flex', gap: '50px', alignItems: 'center', perspective: '1400px' })
  panel.innerHTML = '<div class="txt" style="flex:1"><div class="caps who" style="color:var(--coral);font-size:20px"></div><div class="serif one" style="font-size:54px;line-height:1.2;margin-top:14px"></div></div><div class="shot" style="flex:none;width:620px;height:340px;border-radius:16px;overflow:hidden;box-shadow:0 20px 50px rgba(20,33,31,.25);background:#fff;transform-origin:50% 50%"></div>'
  const who = panel.querySelector('.who'), one = panel.querySelector('.one'), shot = panel.querySelector('.shot')
  const imgs = AGENTS.map((a) => {
    const img = h('img', '', null, shot)
    if (a.snap) { img.src = `../recordings/snaps/step${a.snap}.png`; css(img, { width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 20%', display: 'none' }) }
    else { css(img, { width: '1600px', height: '900px', display: 'none', transformOrigin: '0 0', transform: 'scale(0.81) translate(-460px, -60px)' }) }
    return img
  })
  const others = ['Saathi · answers safety questions', 'Watch · reads weather alerts', 'Planner · keeps every step on record'].map((txt) => {
    const el = h('div', 'abs chip', txt, root)
    css(el, { background: 'var(--ink)', color: '#fff', fontSize: '28px', padding: '16px 28px' })
    return el
  })
  const burst = h('div', 'abs', '', root)
  return (t) => {
    const intro = L(sc, 0)
    show(head, E.out(prog(t, 0, 0.7)), { y: -40, blur: 8 })
    track.style.opacity = clamp(prog(t, 1.2, 2.2))
    // Agents burst from the centre to their places.
    nodes.forEach((n, i) => {
      const q = E.back(prog(t, 0.8 + i * 0.18, 1.8 + i * 0.18))
      const cx = 960 - 59, cy = 560
      const x = lerp(cx, n._x, clamp(q)), y = lerp(cy, 245, clamp(q))
      const spin = (1 - clamp(q)) * 360
      let active = -1
      for (let k = 1; k <= 5; k++) { const w = L(sc, k); if (t >= w.a - 0.3 && t < w.b - 0.3) active = k - 1 }
      const on = active === i
      const dim = t > L(sc, 6).a - 0.3 ? 0.35 : active >= 0 && !on ? 0.55 : 1
      css(n, { left: x + 'px', top: y + 'px', opacity: clamp(q * 2) * dim, transform: `rotate(${spin}deg) scale(${on ? 1.22 : 1})` })
    })
    // Pulse travels to the active agent.
    let px = 120, act = -1
    for (let k = 1; k <= 5; k++) { const w = L(sc, k); if (t >= w.a - 0.4) { act = k - 1 } }
    if (act >= 0) {
      const w = L(sc, act + 1), from = act > 0 ? nodes[act - 1]._x + 59 : 120, to = nodes[act]._x + 59
      px = lerp(from, to, E.io(prog(t, w.a - 0.4, w.a + 0.4)))
    }
    css(pulse, { left: px - 13 + 'px', opacity: act >= 0 && t < L(sc, 6).a ? 1 : 0, transform: `scale(${1 + 0.25 * Math.sin(t * 6)})` })
    // Showcase panel.
    if (act >= 0 && t < L(sc, 6).a - 0.2) {
      const w = L(sc, act + 1), a = AGENTS[act]
      const q = E.out(prog(t, w.a - 0.35, w.a + 0.35))
      panel.style.opacity = clamp(prog(t, L(sc, 1).a - 0.4, L(sc, 1).a)) * (1 - prog(t, L(sc, 6).a - 0.5, L(sc, 6).a - 0.2))
      who.textContent = `${a.n}${a.human ? ' · a human' : ' · agent'}`
      one.textContent = a.one
      one.style.transform = `translateY(${(1 - q) * 40}px)`; one.style.opacity = q
      shot.style.transform = `rotateY(${(1 - q) * 70}deg) scale(${lerp(0.8, 1, q)})`
      imgs.forEach((img, k) => { img.style.display = k === act ? 'block' : 'none' })
      if (!a.snap) setImg(imgs[act], framePath('rescue', 'dash', ev('rescue', 'route preview').c + 3.5))
    } else panel.style.opacity = 0
    // The other three orbit.
    const ow = L(sc, 6)
    others.forEach((o, i) => {
      const q = E.back(prog(t, ow.a - 0.2 + i * 0.45, ow.a + 0.4 + i * 0.45))
      const ang = t * 0.45 + i * (Math.PI * 2 / 3)
      const x = 960 + Math.cos(ang) * 560 - 230, y = 700 + Math.sin(ang) * 170
      css(o, { left: x + 'px', top: y + 'px', opacity: clamp(q), transform: `scale(${lerp(0.3, 1, clamp(q))})` })
    })
  }
}

// ---------- 5. Login ----------
builders.login = (root, sc) => {
  const lap = Device(root, 'laptop', 'login', 'desk', { x: 300, y: 150, scale: 0.8, label: 'The real app · screen recording' })
  const live = h('div', 'live', '<i></i> LIVE · REAL APP', root)
  css(live, { left: '840px', top: '70px' })
  const signin = ev('login', 'Sign in')
  return (t) => {
    const d = sc.end - sc.start
    const q = E.out(prog(t, 0, 0.9))
    lap.root.style.transform = `perspective(1600px) rotateX(${(1 - q) * 55}deg) translateY(${(1 - q) * 300}px) scale(${lerp(0.7, 1, q)})`
    lap.root.style.opacity = clamp(q * 1.5)
    const c = lerp(0.6, signin.c + 2.2, prog(t, 0.3, d - 0.3))
    lap.set(c, camAt([[0, 1, 800, 450], [d * 0.55, 1.6, 1000, 520], [d, 1.1, 800, 450]], t))
    live.style.opacity = clamp(prog(t, 0.5, 1))
  }
}

// Map scene-local time to clip clock through beat segments: [[a, b, c0, c1], ...]
function segClock(segs, t) {
  for (const [a, b, c0, c1] of segs) if (t < b) return lerp(c0, c1, prog(t, a, b))
  const s = segs[segs.length - 1]
  return s[3]
}

// ---------- 6. One rescue, three screens, in sync ----------
builders.rescue = (root, sc) => {
  const lap = Device(root, 'laptop', 'rescue', 'dash', { x: 60, y: 200, scale: 0.66, label: 'Control room · officer' })
  const kam = Device(root, 'phone', 'rescue', 'phone', { x: 1215, y: 175, scale: 0.76, label: 'Kamla’s phone' })
  const crew = Device(root, 'phone', 'rescue', 'crew', { x: 1565, y: 175, scale: 0.76, label: 'Boat 1 crew' })
  const live = h('div', 'live', '<i></i> LIVE · ALL THREE SCREENS IN SYNC', root)
  css(live, { left: '640px', top: '96px' })
  const beam = h('div', 'abs', null, root)
  css(beam, { height: '6px', borderRadius: '3px', background: 'linear-gradient(90deg, transparent, var(--coral), transparent)', top: '560px' })
  const stamp = h('div', 'stamp', 'SAFE ✓', root)
  css(stamp, { left: '420px', top: '460px', color: 'var(--green)', borderColor: 'var(--green)' })
  const E1 = (l) => ev('rescue', l).c
  const beats = ['send', 'merge', 'detail', 'approve', 'accept', 'safe']
  const ranges = {
    send: [E1('I am Kamla Devi') + 0.5, E1('Kamla sends') + 2.6],
    merge: [E1('ticket appears') - 0.6, E1('neighbour') + 3.4],
    detail: [E1('Open the ticket') - 0.5, E1('Why P1') + 2.0],
    approve: [E1('route preview') - 0.3, E1('Approve Boat 1') + 1.8],
    accept: [E1('Crew accepts') - 1.0, E1('OTP') + 1.6],
    safe: [E1('Boat reached') - 0.4, E1('Family confirmed') + 3.6],
  }
  const segs = beats.map((b, i) => { const w = L(sc, i); return [w.a, w.b, ranges[b][0], ranges[b][1]] })
  segs.unshift([-0.5, 0, ranges.send[0] - 0.3, ranges.send[0]])
  const cam = (() => {
    const k = (i, f) => L(sc, i).a + (L(sc, i).b - L(sc, i).a) * f
    return [[0, 1, 800, 450], [k(1, 0), 1, 800, 450], [k(1, 0.25), 1.7, 260, 470], [k(1, 0.95), 1.7, 260, 470],
      [k(2, 0.15), 1.55, 690, 700], [k(2, 0.95), 1.55, 690, 700], [k(3, 0.12), 1.8, 1390, 170], [k(3, 0.6), 1.8, 1330, 200],
      [k(3, 0.9), 1.0, 800, 450], [k(5, 0.9), 1.0, 800, 450]]
  })()
  return (t) => {
    const c = segClock(segs, t)
    lap.set(c, camAt(cam, t)); kam.set(c); crew.set(c)
    const enter = E.out(prog(t, -0.3, 0.8))
    lap.root.style.transform = `translateX(${(1 - enter) * -900}px) rotate(${(1 - enter) * -8}deg)`
    kam.root.style.transform = `translateY(${(1 - enter) * 900}px)`
    crew.root.style.transform = `translateY(${(1 - enter) * 1100}px)`
    const focus = (dev, on) => { dev.root.style.filter = on ? 'drop-shadow(0 0 30px rgba(212,112,95,.55))' : '' ; dev.root.style.transform += ` scale(${on ? 1.06 : 1})` }
    const w = (i) => L(sc, i)
    focus(kam, (t >= w(0).a && t < w(0).b) || (t >= w(4).a + (w(4).b - w(4).a) * 0.45 && t < w(4).b))
    focus(crew, (t >= w(4).a && t < w(4).a + (w(4).b - w(4).a) * 0.45) || t >= w(5).a)
    focus(lap, t >= w(1).a && t < w(4).a)
    live.style.opacity = clamp(prog(t, 0, 0.8))
    // "Same moment" beam from the crew phone to Kamla's phone when the boat sets off.
    const bq = prog(t, w(4).a + (w(4).b - w(4).a) * 0.35, w(4).a + (w(4).b - w(4).a) * 0.6)
    css(beam, { left: lerp(1700, 1250, bq) + 'px', width: '260px', opacity: bq > 0 && bq < 1 ? 1 : 0 })
    const conf = E1('Family confirmed') + 0.5
    const sq = E.elastic(prog(c, conf, conf + 0.9))
    stamp.style.opacity = t >= w(5).a ? clamp(prog(c, conf - 0.05, conf + 0.2)) : 0
    stamp.style.transform = `rotate(-8deg) scale(${lerp(3, 1, clamp(sq))})`
  }
}

// ---------- 7. Hard cases ----------
builders.signals = (root, sc) => {
  const E2 = (l) => ev('signals', l).c
  const lapA = Device(root, 'laptop', 'signals', 'dash', { x: 240, y: 170, scale: 0.86, label: 'Control room' })
  const phone = Device(root, 'phone', 'signals', 'phone', { x: 360, y: 150, scale: 0.98, label: 'A resident on Gali 7' })
  const crew = Device(root, 'phone', 'signals', 'crew', { x: 140, y: 190, scale: 0.86, label: 'Boat 1 crew' })
  const lapB = Device(root, 'laptop', 'signals', 'dash', { x: 640, y: 230, scale: 0.7, label: 'Control room' })
  const verify = h('div', 'stamp', 'HELD FOR VERIFY', root)
  css(verify, { left: '1180px', top: '120px', color: 'var(--slate)', borderColor: 'var(--slate)', fontSize: '52px' })
  const gas = h('div', 'abs', '<div class="serif" style="font-size:280px;font-weight:700;color:var(--brick);line-height:1">1906</div><div style="font-size:38px;color:var(--ink);max-width:760px;line-height:1.3">Saathi answers with the emergency number <b>first</b>, then safe steps from a vetted playbook.</div>', root)
  css(gas, { left: '930px', top: '300px' })
  const road = h('div', 'stamp', 'LANE 6 BLOCKED → REROUTED', root)
  css(road, { left: '720px', top: '110px', fontSize: '46px', color: 'var(--brick)', borderColor: 'var(--brick)' })
  const groups = [[lapA, verify], [phone, gas], [crew, lapB, road], [lapA]]
  const ranges = [
    [E2('rumour arrives') - 0.6, E2('Back to active') + 0.3],
    [E2('Gas leak question') - 3.2, E2('Saathi replies') + 1.6],
    [E2('Crew reports') - 0.6, E2('map turns') + 3.4],
    [E2('Chat opens') - 0.6, E2('Back to control') - 0.2],
  ]
  const segs = ranges.map((r, i) => { const w = L(sc, i); return [w.a, w.b, r[0], r[1]] })
  return (t) => {
    const c = segClock(segs, t)
    let beat = 0
    for (let i = 0; i < 4; i++) if (t >= L(sc, i).a - 0.35) beat = i
    const all = [lapA, phone, crew, lapB, verify, gas, road]
    all.forEach((el) => { const r = el.root || el; r.style.display = groups[beat].includes(el) ? 'block' : 'none' })
    const w = L(sc, beat)
    // Whip in: a fast slide with motion blur.
    const q = E.out(prog(t, w.a - 0.35, w.a + 0.25))
    for (const el of groups[beat]) {
      const r = el.root || el
      r.style.filter = `blur(${(1 - q) * 18}px)`
      r.style.transform = `translateX(${(1 - q) * 1400}px) skewX(${(1 - q) * -12}deg)`
    }
    if (beat === 0) { lapA.set(c, camAt([[w.a, 1, 800, 450], [w.a + 1.5, 1.7, 260, 560], [w.b, 1.7, 230, 650]], t)); verify.style.transform += ` rotate(-6deg) scale(${lerp(2.5, 1, E.elastic(prog(t, w.a + 1.6, w.a + 2.6)))})`; verify.style.opacity = clamp(prog(t, w.a + 1.5, w.a + 1.8)) }
    if (beat === 1) { phone.set(c); gas.style.opacity = clamp(prog(t, w.a + 2.4, w.a + 2.9)); gas.style.transform += ` scale(${lerp(1.6, 1, E.back(prog(t, w.a + 2.4, w.a + 3.0)))})` }
    if (beat === 2) { crew.set(c); lapB.set(c, camAt([[w.a, 1, 800, 450], [w.a + 1.6, 1.5, 820, 440], [w.b, 1.5, 820, 440]], t)); road.style.opacity = clamp(prog(t, w.a + 2.2, w.a + 2.6)) }
    if (beat === 3) { lapA.set(c, camAt([[w.a, 1.15, 500, 450], [w.b, 1.15, 500, 450]], t)) }
  }
}

// ---------- 8. Family lookup ----------
builders.family = (root, sc) => {
  const ph = Device(root, 'phone', 'family', 'phone', { x: 300, y: 110, scale: 0.9, label: 'A relative, anywhere' })
  const txt = h('div', 'abs', '', root)
  css(txt, { left: '900px', top: '260px', width: '880px' })
  txt.innerHTML = `<div class="caps" style="color:var(--coral);font-size:20px">Is my family safe?</div>
    <div class="serif" style="font-size:64px;line-height:1.15;margin-top:14px">Status and camp.<br/>Nothing else.</div>
    <div style="display:flex;gap:16px;margin-top:40px;flex-wrap:wrap">
      <span class="chip x1" style="background:rgba(200,68,60,.1);color:var(--brick);font-size:30px;text-decoration:line-through">House address</span>
      <span class="chip x2" style="background:rgba(200,68,60,.1);color:var(--brick);font-size:30px;text-decoration:line-through">Phone number</span></div>
    <div class="chip ok" style="margin-top:22px;background:rgba(79,138,76,.14);color:#3c6e3a;font-size:32px">${icon('check', 30, 2.4)} Rescued · safe at Camp 3</div>`
  const x1 = txt.querySelector('.x1'), x2 = txt.querySelector('.x2'), ok = txt.querySelector('.ok')
  return (t) => {
    const d = sc.end - sc.start
    const q = E.out(prog(t, -0.3, 0.7))
    ph.root.style.transform = `perspective(1400px) rotateY(${(1 - q) * -70}deg) translateX(${(1 - q) * -300}px)`
    ph.set(lerp(0.5, ev('family', 'Search').c + 4.5, prog(t, 0.2, d - 1)))
    show(txt, E.out(prog(t, 0.3, 1.0)), { x: 120, y: 0 })
    ;[x1, x2, ok].forEach((el, i) => { const p = E.back(prog(t, 2.5 + i * 1.3, 3.1 + i * 1.3)); el.style.opacity = clamp(p); el.style.transform = `scale(${lerp(0.5, 1, clamp(p))})` })
  }
}

// ---------- 9. A whole night at 10x ----------
builders.replay = (root, sc) => {
  const lap = Device(root, 'laptop', 'replay', 'dash', { x: 160, y: 120, scale: 0.98 })
  const badge = h('div', 'live', '<i></i> A WHOLE FLOOD NIGHT · 10× SPEED', root)
  css(badge, { left: '660px', top: '48px' })
  return (t) => {
    const d = sc.end - sc.start
    const q = E.out(prog(t, -0.3, 0.8))
    lap.root.style.transform = `scale(${lerp(1.4, 1, q)})`
    lap.root.style.filter = `blur(${(1 - q) * 14}px)`
    lap.set(lerp(2.6, D.clips.replay.dash.frames / D.fps - 1.2, E.io(prog(t, 0, d))), camAt([[0, 1, 800, 450], [d * 0.5, 1.25, 900, 420], [d, 1, 800, 450]], t))
    badge.style.opacity = clamp(prog(t, 0.4, 0.9))
  }
}

// ---------- 10. Safety ----------
builders.safety = (root, sc) => {
  const head = h('div', 'abs serif', 'Safety is built in, <span style="color:var(--coral)">not bolted on.</span>', root)
  css(head, { left: '120px', top: '140px', fontSize: '64px', fontWeight: 600 })
  const items = [
    { i: 'up', t: 'Agents raise a priority', s: 'but never lower one' },
    { i: 'lock', t: 'No boat, no bulletin', s: 'without an officer’s approval' },
    { i: 'list', t: 'Every action on record', s: 'with the name of who approved it' },
    { i: 'shield', t: 'One switch stops it all', s: 'automation off, instantly' },
  ].map((it, k) => {
    const el = h('div', 'abs card', `<div style="width:92px;height:92px;border-radius:24px;background:var(--ink);color:#fff;display:flex;align-items:center;justify-content:center">${icon(it.i, 50, 1.8, '#fff')}</div><div class="serif" style="font-size:40px;font-weight:600;margin-top:26px">${it.t}</div><div style="font-size:28px;color:var(--muted);margin-top:6px">${it.s}</div>`, root)
    css(el, { left: 120 + (k % 2) * 850 + 'px', top: 300 + Math.floor(k / 2) * 330 + 'px', width: '810px', height: '290px', padding: '34px 40px' })
    return el
  })
  const toggle = h('div', 'abs', '<div class="sw" style="width:150px;height:76px;border-radius:40px;position:relative"><i style="position:absolute;top:8px;width:60px;height:60px;border-radius:50%;background:#fff;box-shadow:0 4px 10px rgba(0,0,0,.2)"></i></div>', items[3])
  css(toggle, { right: '40px', top: '40px' })
  const sw = toggle.querySelector('.sw'), knob = toggle.querySelector('i')
  return (t) => {
    show(head, E.out(prog(t, 0, 0.8)), { y: -50, blur: 10 })
    const w = L(sc, 1)
    items.forEach((el, k) => {
      const a = w.a + (w.e - w.a) * [0.0, 0.3, 0.56, 0.78][k]
      const q = E.back(prog(t, a - 0.25, a + 0.45))
      el.style.opacity = clamp(q)
      el.style.transform = `perspective(1200px) rotateX(${(1 - clamp(q)) * -80}deg) translateY(${(1 - clamp(q)) * 80}px)`
    })
    const off = prog(t, w.a + (w.e - w.a) * 0.86, w.a + (w.e - w.a) * 0.9)
    sw.style.background = off > 0.5 ? 'var(--brick)' : 'var(--green)'
    knob.style.left = lerp(82, 8, E.io(off)) + 'px'
  }
}

// ---------- 11. Under the hood ----------
function highlight(src) {
  return esc(src)
    .replace(/(#.*)$/gm, '<span class="tk-c">$1</span>')
    .replace(/("[^"\n]*"|'[^'\n]*'|f"[^"\n]*")/g, '<span class="tk-s">$1</span>')
    .replace(/\b(def|if|not|raise|return|and|or|in|is|None|for|with|elif|else|import|from|True|False)\b/g, '<span class="tk-k">$1</span>')
    .replace(/\b([a-z_]+)(?=\()/g, '<span class="tk-f">$1</span>')
}
function codeWin(parent, title, src, { x, y, w, hl = [] }) {
  const el = h('div', 'code', null, parent)
  css(el, { left: x + 'px', top: y + 'px', width: w + 'px' })
  el.innerHTML = `<div class="bar"><i style="background:#d4705f"></i><i style="background:#c68a2e"></i><i style="background:#4f8a4c"></i>&nbsp; ${title}</div><pre></pre>`
  const pre = el.querySelector('pre')
  const lines = src.split('\n')
  pre.innerHTML = lines.map((l, i) => `<span class="ln${hl.some((r) => r.test(l)) ? ' hl' : ''}">${highlight(l) || ' '}</span>`).join('')
  return { el, lines: [...pre.querySelectorAll('.ln')] }
}
builders.tech = (root, sc) => {
  const head = h('div', 'abs serif', 'Under the hood: <span style="color:var(--coral)">simple on purpose.</span>', root)
  css(head, { left: '120px', top: '120px', fontSize: '56px', fontWeight: 600 })
  // Tree.
  const tree = codeWin(root, 'PROJECT STRUCTURE', D.tree.join('\n'), { x: 120, y: 240, w: 1100, hl: [/agents\//, /tools\//, /approvals\.py/] })
  const treeNote = h('div', 'abs', '<div class="caps" style="color:var(--coral);font-size:18px">The rule of the codebase</div><div class="serif" style="font-size:44px;line-height:1.25;margin-top:12px">Agents never touch the world directly.<br/>They call small tools, and the tools enforce the rules.</div>', root)
  css(treeNote, { left: '1280px', top: '300px', width: '540px' })
  // Stack diagram.
  const stack = h('div', 'abs', '', root)
  css(stack, { left: '120px', top: '250px', width: '1680px', height: '700px' })
  stack.innerHTML = `
    <div class="col screens" style="position:absolute;left:0;top:40px;width:400px">
      ${[['laptop', 'Control room', 'officer’s laptop'], ['phone', 'Helpline chat', 'any family’s phone'], ['boat', 'Crew desk', 'boat and van phones']].map(([i, a, b]) => `<div class="card" style="display:flex;gap:18px;align-items:center;padding:20px 24px;margin-bottom:22px">${icon(i, 44, 1.7, '#2f5d58')}<div><div class="serif" style="font-size:28px;font-weight:600">${a}</div><div style="font-size:20px;color:var(--muted)">${b}</div></div></div>`).join('')}
      <div class="chip" style="background:var(--ink);color:#fff;font-size:20px">React · Vite · Tailwind · Leaflet</div>
    </div>
    <div style="position:absolute;left:470px;top:150px;width:360px;text-align:center"><div class="caps" style="font-size:18px;color:var(--coral)">Live event stream</div><div style="font-size:22px;color:var(--muted)">server-sent events, every screen at once</div></div>
    <svg style="position:absolute;left:430px;top:230px" width="440" height="160"><path class="pipe" d="M0 80 H440" stroke="#2f5d58" stroke-width="5" stroke-dasharray="14 10" fill="none"/><path d="M0 110 H440" stroke="#d4705f" stroke-width="5" stroke-dasharray="14 10" fill="none" class="pipe2"/></svg>
    <div class="card core" style="position:absolute;left:880px;top:20px;width:520px;height:460px;padding:30px">
      <div class="caps" style="font-size:18px;color:var(--coral)">Python · FastAPI</div>
      <div class="serif" style="font-size:36px;font-weight:600;margin-top:8px">Agents + tools + the human gate</div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:22px">${['Planner', 'Listen', 'Triage', 'Dispatch', 'Loop', 'Saathi', 'Watch'].map((a) => `<span class="chip" style="font-size:20px;background:rgba(47,93,88,.12);color:var(--teal)">${a}</span>`).join('')}</div>
      <div style="margin-top:26px;padding:16px 20px;border-radius:16px;background:rgba(212,112,95,.12);font-size:24px;display:flex;gap:12px;align-items:center">${icon('lock', 32, 2, '#c8443c')} approvals.require_approved()</div>
    </div>
    <div class="card" style="position:absolute;left:1440px;top:60px;width:240px;padding:24px;text-align:center">${icon('list', 44, 1.7, '#2f5d58')}<div class="serif" style="font-size:28px;font-weight:600;margin-top:6px">SQLite</div><div style="font-size:18px;color:var(--muted)">tickets · audit log</div></div>
    <div class="card llm" style="position:absolute;left:1440px;top:300px;width:240px;padding:24px;text-align:center;border-style:dashed">${icon('laptop', 44, 1.7, '#2f5d58')}<div class="serif" style="font-size:26px;font-weight:600;margin-top:6px">Ollama</div><div style="font-size:18px;color:var(--muted)">local model, optional</div></div>`
  const pipe = stack.querySelector('.pipe'), pipe2 = stack.querySelector('.pipe2')
  const stackParts = [...stack.children]
  // Local.
  const local = h('div', 'abs', '', root)
  css(local, { left: '120px', top: '280px', width: '1680px' })
  local.innerHTML = `<div style="display:flex;gap:40px;align-items:stretch">
    ${[['laptop', 'One laptop', 'the whole control room runs here'], ['cloudx', 'No cloud AI', 'messages never leave the ward'], ['check', 'Rules mode', 'works with no model at all'], ['chat', 'Or Ollama', 'a local model, if there is one']].map(([i, a, b]) => `<div class="card lc" style="flex:1;padding:40px 34px;text-align:center"><div style="color:var(--teal)">${icon(i, 90, 1.5)}</div><div class="serif" style="font-size:40px;font-weight:600;margin-top:18px">${a}</div><div style="font-size:24px;color:var(--muted);margin-top:8px">${b}</div></div>`).join('')}</div>`
  const lcs = [...local.querySelectorAll('.lc')]
  // Code.
  const guard = codeWin(root, 'backend/app/tools/approvals.py', D.code.guard, { x: 100, y: 230, w: 1180, hl: [/raise ApprovalRequired/] })
  guard.el.style.fontSize = '17.5px'
  const assign = codeWin(root, 'backend/app/tools/teams.py', D.code.assign, { x: 1010, y: 500, w: 860, hl: [/require_approved/] })
  assign.el.style.fontSize = '14.5px'
  // Tests.
  const term = h('div', 'code', '<div class="bar"><i style="background:#d4705f"></i><i style="background:#c68a2e"></i><i style="background:#4f8a4c"></i>&nbsp; TERMINAL</div><pre class="tp"></pre>', root)
  css(term, { left: '260px', top: '260px', width: '1400px', height: '560px' })
  const tp = term.querySelector('.tp')
  const big = h('div', 'abs serif', '67 passed', root)
  css(big, { left: '50%', top: '560px', transform: 'translateX(-50%)', fontSize: '170px', fontWeight: 700, color: '#7fd68a', textShadow: '0 10px 40px rgba(0,0,0,.4)', whiteSpace: 'nowrap' })
  return (t) => {
    const w0 = L(sc, 0), wt = L(sc, 1), ws = L(sc, 2), wl = L(sc, 3), wc = L(sc, 4), wx = L(sc, 5)
    show(head, E.out(prog(t, 0, 0.7)), { y: -40, blur: 10 })
    head.style.opacity = 1
    const vis = (el, a, b) => { const p = clamp(prog(t, a - 0.3, a + 0.3)) * (1 - prog(t, b - 0.3, b)); el.style.opacity = p; return p }
    const p1 = vis(tree.el, wt.a, wt.b); vis(treeNote, wt.a + 1.2, wt.b)
    tree.el.style.transform = `translateX(${(1 - E.out(clamp(p1))) * -200}px)`
    tree.lines.forEach((ln, i) => { ln.style.opacity = clamp(prog(t, wt.a + i * 0.22, wt.a + i * 0.22 + 0.2)) })
    treeNote.style.transform = `translateY(${(1 - E.out(prog(t, wt.a + 1.2, wt.a + 2))) * 60}px)`
    vis(stack, ws.a, ws.b)
    stackParts.forEach((el, i) => { const q = E.back(prog(t, ws.a + i * 0.45, ws.a + i * 0.45 + 0.6)); el.style.opacity = clamp(q); el.style.transform = `translateY(${(1 - clamp(q)) * 80}px) scale(${lerp(0.8, 1, clamp(q))})` })
    pipe.style.strokeDashoffset = -t * 120; pipe2.style.strokeDashoffset = t * 120
    vis(local, wl.a, wl.b)
    lcs.forEach((el, i) => { const q = E.back(prog(t, wl.a + i * 0.9, wl.a + i * 0.9 + 0.6)); el.style.opacity = clamp(q); el.style.transform = `rotate(${(1 - clamp(q)) * (i % 2 ? 10 : -10)}deg) translateY(${(1 - clamp(q)) * 120}px)` })
    const pg = vis(guard.el, wc.a, wc.b), pa = vis(assign.el, wc.a + 3.2, wc.b)
    guard.el.style.transform = `perspective(1600px) rotateY(${(1 - E.out(clamp(pg))) * 40}deg)`
    assign.el.style.transform = `translateY(${(1 - E.out(clamp(pa))) * 200}px)`
    guard.lines.forEach((ln, i) => { ln.style.opacity = clamp(prog(t, wc.a + i * 0.16, wc.a + i * 0.16 + 0.15)) })
    vis(term, wx.a, wx.b + 0.4)
    const dots = Math.floor(67 * E.io(prog(t, wx.a + 0.4, wx.a + 2.0)))
    tp.textContent = `$ pytest -q\n\n${'.'.repeat(dots).replace(/(.{50})/g, '$1\n')}\n\n${dots >= 67 ? '67 passed in 25.3s' : ''}`
    const bq = E.elastic(prog(t, wx.a + 2.0, wx.a + 3.0))
    big.style.opacity = clamp(prog(t, wx.a + 1.9, wx.a + 2.2))
    big.style.transform = `translateX(-50%) scale(${lerp(0.2, 1, clamp(bq))})`
  }
}

// ---------- 12. Results ----------
builders.results = (root, sc) => {
  const head = h('div', 'abs serif', 'One flood night. <span style="color:var(--coral)">Two ways.</span>', root)
  css(head, { left: '120px', top: '130px', fontSize: '60px', fontWeight: 600 })
  const rows = [
    { t: 'Minutes to send a boat to the most urgent families', a: 463, b: 20 },
    { t: 'Wasted trips', a: 131, b: 15 },
    { t: 'Rumours caught (of 15)', a: 0, b: 15, up: true },
  ].map((r, k) => {
    const el = h('div', 'abs', `<div style="font-size:30px;font-weight:600">${r.t}</div>
      <div style="display:flex;align-items:center;gap:20px;margin-top:14px"><span class="caps" style="width:200px;font-size:16px;color:var(--muted)">First come</span><span style="flex:1;height:26px;background:rgba(31,61,57,.08);border-radius:13px;overflow:hidden"><i class="ba" style="display:block;height:100%;background:#9aaba5;width:0"></i></span><span class="serif na" style="width:150px;text-align:right;font-size:40px;color:var(--muted)">0</span></div>
      <div style="display:flex;align-items:center;gap:20px;margin-top:10px"><span class="caps" style="width:200px;font-size:16px;color:var(--ink)">Pukaar</span><span style="flex:1;height:26px;background:rgba(31,61,57,.08);border-radius:13px;overflow:hidden"><i class="bb" style="display:block;height:100%;background:var(--coral);width:0"></i></span><span class="serif nb" style="width:150px;text-align:right;font-size:52px;font-weight:700">0</span></div>`, root)
    css(el, { left: '120px', top: 260 + k * 215 + 'px', width: '1340px' })
    el._r = r
    return el
  })
  const x23 = h('div', 'stamp', '23× faster', root)
  css(x23, { left: '1500px', top: '300px', fontSize: '58px' })
  const note = h('div', 'abs', 'Simulated 311-message night with known answers, rules mode. Pukaar reached 25 of the 28 most urgent families within the night.', root)
  css(note, { left: '120px', top: '930px', fontSize: '22px', color: 'var(--muted)', width: '1500px' })
  return (t) => {
    show(head, E.out(prog(t, 0, 0.7)), { y: -40 })
    const starts = [L(sc, 1).a, L(sc, 2).a, L(sc, 2).a + (L(sc, 2).e - L(sc, 2).a) * 0.6]
    rows.forEach((el, k) => {
      const r = el._r, a0 = starts[k]
      show(el, E.out(prog(t, a0 - 0.4, a0)), { x: -100, y: 0 })
      const qa = E.out(prog(t, a0, a0 + 1.2)), qb = E.out(prog(t, a0 + 1.0, a0 + 2.4))
      const max = Math.max(r.a, r.b, 1)
      el.querySelector('.ba').style.width = (r.a / max) * 100 * qa + '%'
      el.querySelector('.bb').style.width = (r.b / max) * 100 * qb + '%'
      el.querySelector('.na').textContent = Math.round(r.a * qa)
      el.querySelector('.nb').textContent = Math.round(r.b * qb)
    })
    const q = E.elastic(prog(t, starts[0] + 2.6, starts[0] + 3.6))
    x23.style.opacity = clamp(prog(t, starts[0] + 2.5, starts[0] + 2.8))
    x23.style.transform = `rotate(-8deg) scale(${lerp(3, 1, clamp(q))})`
    note.style.opacity = clamp(prog(t, starts[1], starts[1] + 1))
  }
}

// ---------- 13. Beyond floods ----------
builders.beyond = (root, sc) => {
  const core = h('div', 'abs', `<div style="width:260px;height:260px;border-radius:50%;background:var(--ink);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 30px 70px rgba(20,33,31,.3)">${LOGO(90, '#d4705f')}<div class="serif" style="font-size:30px;font-weight:600;margin-top:10px">7 agents</div><div class="caps sw" style="font-size:15px;color:#f0b3a6">Flood</div></div>`, root)
  css(core, { left: '830px', top: '400px' })
  const swap = core.querySelector('.sw')
  const ring = h('div', 'abs', null, root)
  css(ring, { left: '760px', top: '330px', width: '400px', height: '400px', borderRadius: '50%', border: '3px dashed rgba(47,93,88,.35)' })
  const head = h('div', 'abs serif', 'Same agents. <span style="color:var(--coral)">New map. New playbooks.</span>', root)
  css(head, { left: '50%', top: '130px', transform: 'translateX(-50%)', fontSize: '58px', fontWeight: 600, whiteSpace: 'nowrap' })
  const cards = [
    { i: 'wind', t: 'Cyclone', a: 'Watch', s: 'moves boats before landfall', x: 120, y: 300 },
    { i: 'quake', t: 'Earthquake', a: 'Triage', s: 'ranks people trapped under rubble', x: 1300, y: 300 },
    { i: 'sun', t: 'Heatwave', a: 'Saathi', s: 'points people to the nearest cooling centre', x: 120, y: 640 },
    { i: 'flame', t: 'Fire', a: 'Dispatch', s: 'routes crews around the smoke', x: 1300, y: 640 },
  ].map((c) => {
    const el = h('div', 'abs card', `<div style="display:flex;gap:22px;align-items:center"><div style="width:96px;height:96px;border-radius:26px;background:rgba(212,112,95,.14);color:var(--coral);display:flex;align-items:center;justify-content:center">${icon(c.i, 56, 1.7)}</div><div><div class="serif" style="font-size:44px;font-weight:600">${c.t}</div><div style="font-size:26px;color:var(--muted)"><b style="color:var(--teal)">${c.a}</b> ${c.s}</div></div></div>`, root)
    css(el, { left: c.x + 'px', top: c.y + 'px', width: '500px', padding: '30px 34px' })
    return el
  })
  const names = ['Flood', 'Cyclone', 'Earthquake', 'Heatwave', 'Fire']
  return (t) => {
    show(head, E.out(prog(t, 0, 0.8)), { y: -40, blur: 10 })
    head.style.transform += ' translateX(-50%)'; head.style.left = '50%'
    const cq = E.elastic(prog(t, 0.2, 1.4))
    core.style.transform = `scale(${clamp(cq, 0, 2)}) rotate(${Math.sin(t * 2) * 3}deg)`
    ring.style.transform = `rotate(${t * 30}deg)`
    const w = L(sc, 2)
    let k = 0
    cards.forEach((el, i) => {
      const a = w.a + (w.e - w.a) * (i * 0.25)
      if (t >= a) k = i + 1
      const q = E.back(prog(t, a - 0.25, a + 0.5))
      el.style.opacity = clamp(q)
      el.style.transform = `translate(${(1 - clamp(q)) * (i % 2 ? 300 : -300)}px, 0) rotate(${(1 - clamp(q)) * (i % 2 ? 12 : -12)}deg)`
    })
    swap.textContent = names[t < L(sc, 1).a + 1 ? 0 : t < w.a ? Math.floor(t * 3) % 5 : k]
  }
}

// ---------- 14. Outro ----------
builders.outro = (root, sc) => {
  const rings = Array.from({ length: 4 }, () => { const r = h('div', 'abs', null, root); css(r, { borderRadius: '50%', border: '3px solid var(--coral)' }); return r })
  const logo = h('div', 'center', LOGO(180), root)
  const line = h('div', 'abs serif', 'Pukaar means <i>a call for help</i>.<br/>We make sure every one is answered.', root)
  css(line, { left: '50%', top: '700px', transform: 'translateX(-50%)', fontSize: '56px', textAlign: 'center', width: '1600px', lineHeight: 1.3 })
  const team = h('div', 'abs caps', 'Team Seekers', root)
  css(team, { left: '50%', top: '880px', transform: 'translateX(-50%)', fontSize: '54px', color: 'var(--coral)', whiteSpace: 'nowrap' })
  return (t) => {
    const q = E.elastic(prog(t, 0, 1.2))
    logo.style.transform = `translate(-50%, calc(-50% - 150px)) scale(${clamp(q, 0, 2)})`
    rings.forEach((r, i) => { const p = ((t - i * 0.5) % 2 + 2) % 2 / 2, size = 180 + p * 1100; css(r, { left: 960 - size / 2 + 'px', top: 390 - size / 2 + 'px', width: size + 'px', height: size + 'px', opacity: (1 - p) * 0.5 }) })
    show(line, E.out(prog(t, 0.6, 1.5)), { y: 40 })
    line.style.transform += ' translateX(-50%)'; line.style.left = '50%'
    const tq = E.out(prog(t, L(sc, 1).a - 0.2, L(sc, 1).a + 0.6))
    team.style.opacity = tq
    team.style.letterSpacing = lerp(1.2, 0.3, tq) + 'em'
  }
}

// ---------- build ----------
const RUN = ORDER.map((id) => {
  const sc = SC[id]
  const root = h('div', 'scene', null, scenesEl)
  root.style.display = 'none'
  sc.update = builders[id](root, sc)
  sc.root = root
  return sc
})

// Rain and drifting dust on the effects canvas.
const fx = document.getElementById('fx').getContext('2d')
function drawFx(t) {
  fx.clearRect(0, 0, W, H)
  const cold = SC.cold
  if (t < cold.end + 0.5) {
    const a = 1 - prog(t, cold.end - 0.4, cold.end + 0.5)
    fx.strokeStyle = `rgba(200,230,222,${0.35 * a})`
    fx.lineWidth = 1.6
    for (let i = 0; i < 260; i++) {
      const x = (rand(i) * W + t * 90) % W, y = ((rand(i + 50) * H + t * (900 + rand(i + 7) * 500)) % (H + 60)) - 30
      fx.beginPath(); fx.moveTo(x, y); fx.lineTo(x - 7, y + 26); fx.stroke()
    }
  } else {
    for (let i = 0; i < 46; i++) {
      const x = (rand(i) * W + Math.sin(t * 0.3 + i) * 40), y = (rand(i + 9) * H - t * (8 + rand(i) * 14)) % H
      fx.fillStyle = `rgba(47,93,88,${0.05 + rand(i + 3) * 0.08})`
      fx.beginPath(); fx.arc(x, (y + H) % H, 2 + rand(i + 1) * 4, 0, Math.PI * 2); fx.fill()
    }
  }
}

const bg = document.getElementById('bg'), blobs = [...bg.querySelectorAll('.blob')]
const chrome = document.getElementById('chrome'), chapter = chrome.querySelector('.chapter'), bar = chrome.querySelector('.progress i')
chrome.querySelector('.logo-sm').innerHTML = LOGO(34)
const capIn = document.querySelector('.cap-in'), cap = document.getElementById('cap'), flash = document.getElementById('flash')
let capLine = -1, capWords = []

function seek(t) {
  pending.length = 0
  drawFx(t)
  blobs.forEach((b, i) => { b.style.transform = `translate(${Math.sin(t * 0.13 + i * 2) * 120}px, ${Math.cos(t * 0.11 + i) * 90}px)` })
  for (const sc of RUN) {
    const on = t >= sc.start - 0.4 && t < sc.end + 0.4
    sc.root.style.display = on ? 'block' : 'none'
    if (!on) continue
    const lt = t - sc.start
    sc.update(lt)
    // Scene transitions: zoom-blur in, push-and-fade out.
    const pin = E.out(prog(t, sc.start - 0.4, sc.start + 0.25))
    const pout = E.in(prog(t, sc.end - 0.25, sc.end + 0.4))
    sc.root.style.opacity = Math.min(pin, 1 - pout)
    sc.root.style.transform = `scale(${lerp(1.08, 1, pin) * lerp(1, 0.92, pout)})`
    sc.root.style.filter = pin < 1 || pout > 0 ? `blur(${(1 - pin) * 14 + pout * 14}px)` : ''
  }
  // Flash on the two big moments.
  const hits = [LINES.find((l) => l.caption.includes('eight hours')).start + 0.45, SC.title.start + 0.3]
  flash.style.opacity = Math.max(...hits.map((x) => (t > x && t < x + 0.35 ? 0.55 * (1 - prog(t, x, x + 0.35)) : 0)))
  // Chrome.
  const cur = RUN.find((s) => t >= s.start && t < s.end) || RUN[RUN.length - 1]
  const ch = CHAPTER[cur.id]
  chrome.querySelector('.brand').style.opacity = ['cold', 'title', 'outro'].includes(cur.id) ? 0 : 1
  chapter.innerHTML = ch ? `<em>${ch[0]}</em>${ch[1]}` : ''
  bar.style.width = (t / TOTAL) * 100 + '%'
  bg.style.background = cur.id === 'cold' ? '#0b1916' : ''
  // Captions, word by word.
  const idx = LINES.findIndex((l, i) => t >= l.start - 0.1 && t < (LINES[i + 1] ? Math.min(LINES[i + 1].start - 0.05, l.end + 0.9) : l.end + 1))
  if (idx !== capLine) {
    capLine = idx
    capWords = idx >= 0 ? words(capIn, LINES[idx].caption, 'w') : []
  }
  cap.style.opacity = idx >= 0 ? 1 : 0
  if (idx >= 0) {
    const l = LINES[idx]
    const p = prog(t, l.start, l.end)
    const k = l.hindi ? capWords.length : Math.ceil(p * capWords.length)
    capWords.forEach((w, i) => { w.classList.toggle('on', i < k); w.classList.toggle('now', i === k - 1 && p < 1) })
  }
  return Promise.all(pending)
}

window.TOTAL = TOTAL
window.seek = seek
window.ready = document.fonts.ready.then(() => seek(0))
