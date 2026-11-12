"""Mix the soundtrack: voiceover, an ambient pad that ducks under the voice,
rain for the cold open, whooshes on scene changes, and two accent hits.
Every sound is synthesised here, so there is nothing to license.
Output: build/mix.wav (24 kHz stereo).
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).parent
BUILD = HERE / "build"
SR = 24000
rng = np.random.default_rng(7)

tl = json.loads((BUILD / "lines.json").read_text(encoding="utf-8"))
N = int(tl["total"] * SR)
t = np.arange(N) / SR
voice = np.zeros(N, np.float32)
for line in tl["lines"]:
    a, _ = sf.read(BUILD / "audio" / line["file"], dtype="float32")
    s = int(line["start"] * SR)
    voice[s:s + len(a)] += a[: max(0, N - s)]
voice *= 0.92 / max(1e-6, np.abs(voice).max())


def lowpass(x, cutoff):
    """Two-pole low-pass response applied in the frequency domain."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec /= 1 + (f / cutoff) ** 2
    return np.fft.irfft(spec, n=len(x)).astype(np.float32)


def env(start, attack, hold, release):
    e = np.zeros(N, np.float32)
    a, h, r = int(attack * SR), int(hold * SR), int(release * SR)
    s = int(start * SR)
    seg = np.concatenate([np.linspace(0, 1, max(a, 1)), np.ones(h), np.linspace(1, 0, max(r, 1))]).astype(np.float32)
    if s < 0:
        seg, s = seg[-s:], 0
    seg = seg[: max(0, N - s)]
    e[s:s + len(seg)] = seg
    return e


# Ambient pad: slow chords, each note a pair of slightly detuned sines.
CHORDS = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66], [164.81, 207.65, 246.94]]
pad = np.zeros(N, np.float32)
bar = 7.5
for k in range(int(tl["total"] / bar) + 2):
    chord = CHORDS[k % len(CHORDS)]
    e = env(k * bar - 1.5, 2.5, bar - 1.0, 2.5)
    for f in chord:
        pad += e * (np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.003 * t + 1.1)) * 0.16
    pad += e * np.sin(2 * np.pi * chord[0] / 2 * t) * 0.22
pad *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t) ** 2  # slow swell

# Duck the pad under the voice.
vabs = np.abs(voice)
win = int(0.25 * SR)
vrms = np.sqrt(np.convolve(vabs ** 2, np.ones(win) / win, mode="same"))
duck = 1 - 0.6 * np.clip(vrms / 0.08, 0, 1)
duck = np.convolve(duck, np.ones(win) / win, mode="same")

scenes = []
for line in tl["lines"]:
    if not scenes or scenes[-1][0] != line["scene"]:
        scenes.append((line["scene"], line["start"]))
cold_end = next(s for name, s in scenes if name == "problem")

# Rain and a low drone for the cold open.
noise = rng.standard_normal(N).astype(np.float32)
rain = lowpass(noise[: int((cold_end + 2) * SR)], 1800)
rain = np.pad(rain, (0, N - len(rain)))
rain *= env(0, 1.2, cold_end - 1.2, 2.0) * 0.5
drone = (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.4 * t)) * env(0, 2, cold_end - 2, 2.5) * 0.12

# Whooshes on every scene change: band-limited noise with a quick swell.
sweeps = lowpass(noise, 2600) - lowpass(noise, 300)
whoosh = np.zeros(N, np.float32)
for name, s in scenes[1:]:
    whoosh += sweeps * env(s - 0.55, 0.42, 0.05, 0.35) * 0.55

# Accent hits: a deep thump on the "almost eight hours" line, a chime on the title.
hits = np.zeros(N, np.float32)
_eight = next(l for l in tl["lines"] if "eight hours" in l["caption"])
eight = _eight["start"] + (_eight["end"] - _eight["start"]) * 0.62 + 0.5
title = next(s for name, s in scenes if name == "title")
for when, freqs, decay, gain in [(eight, [55, 82], 6, 0.55), (title, [880, 1318.5, 1760], 2.2, 0.16)]:
    i = int(when * SR)
    seg = np.arange(N - i) / SR
    tone = sum(np.sin(2 * np.pi * f * seg) for f in freqs) * np.exp(-decay * seg) * gain
    hits[i:] += tone.astype(np.float32)

bed = (pad * duck + drone) * 0.5 + rain * 0.35 + whoosh * 0.25 + hits
mix = voice + bed * 0.55
fade = int(1.5 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)
mix /= max(1.0, np.abs(mix).max() / 0.97)
stereo = np.stack([mix, mix], axis=1)
# A touch of width on the bed only.
stereo[:, 1] = voice + np.roll(bed, int(0.012 * SR)) * 0.55
stereo /= max(1.0, np.abs(stereo).max() / 0.97)
sf.write(BUILD / "mix.wav", stereo, SR)
print(f"mix.wav: {tl['total']:.1f}s, {len(scenes)} scenes")
