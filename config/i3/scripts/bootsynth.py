#!/usr/bin/env python3
"""Sound design + live mixer for the boot splash.

build_bank()   -> dict of short synthesized sounds (deep digital palette: bass-heavy squares/triangles, sub layers, 8-bit crush)
Engine         -> streams those sounds to PipeWire the instant boot-anim.py asks for them, mixing overlaps
build_ready()  -> the final "system ready" sound (rendered to a file by make-boot-sounds.py)"""
import fcntl
import shutil
import subprocess
import threading
import time

import numpy as np

SR = 44100
F_SETPIPE_SZ = 1031


# ------------------------------------------------------------------ synthesis primitives
def t(sec):
    return np.arange(int(SR * sec)) / SR


def _phase(f, sec):
    n = int(SR * sec)
    f = np.full(n, f, dtype=float) if np.isscalar(f) else np.asarray(f, dtype=float)[:n]
    return (np.cumsum(f) / SR) % 1.0


def sine(f, sec):
    return np.sin(2 * np.pi * _phase(f, sec))


def square(f, sec, duty=0.5):
    return np.where(_phase(f, sec) < duty, 1.0, -1.0)


def saw(f, sec):
    return 2 * _phase(f, sec) - 1


def tri(f, sec):
    return 2 * np.abs(saw(f, sec)) - 1


def fm(fc, ratio, idx, sec):
    x = t(sec)
    return np.sin(2 * np.pi * fc * x + idx * np.sin(2 * np.pi * fc * ratio * x))


def lowpass(x, k=0.2):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += k * (v - acc)
        y[i] = acc
    return y


def crush(x, bits=6, hold=2):
    levels = 2 ** (bits - 1)
    y = np.round(x * levels) / levels
    if hold > 1:
        y = np.repeat(y[::hold], hold)[: len(x)]
    return y


def gate(n, attack=0.001, release=0.005):
    a, r = max(int(attack * SR), 1), max(int(release * SR), 1)
    g = np.ones(n)
    g[:a] = np.linspace(0, 1, a)
    g[-r:] *= np.linspace(1, 0, r)
    return g


def norm(x, peak):
    return x / (np.abs(x).max() or 1) * peak


def mix(length, events):
    buf = np.zeros(int(SR * length))
    for start, s in events:
        i = int(start * SR)
        j = min(i + len(s), len(buf))
        if i < len(buf):
            buf[i:j] += s[: j - i]
    return buf


# ------------------------------------------------------------------ the sound bank
def build_bank():
    rng = np.random.default_rng(5)
    B = {}

    # kernel-log tick: a short low "thok", 8 pitches so the scroll sounds like data rather than one repeated click
    B["tick"] = []
    for f in (150, 175, 205, 240, 280, 330, 385, 450):
        d = 0.02
        n, x = int(SR * d), t(d)
        body = tri(f, d) * np.exp(-x / 0.007) + 0.6 * sine(f / 2, d) * np.exp(-x / 0.010)
        click = lowpass(rng.standard_normal(n), 0.3) * np.exp(-x / 0.0015)
        B["tick"].append(norm(crush(body * gate(n, 0.0006, 0.006) + 0.5 * click, 6, 2), 0.30))

    # heavy marker every so often, and the buzz for error/warning lines
    d = 0.09
    n, x = int(SR * d), t(d)
    thud = np.sin(2 * np.pi * np.cumsum(np.linspace(95, 42, n)) / SR) * np.exp(-x / 0.03)
    B["thud"] = norm(thud + 0.3 * lowpass(rng.standard_normal(n), 0.3) * np.exp(-x / 0.002), 0.45)
    d = 0.07
    n = int(SR * d)
    B["buzz"] = norm(crush(lowpass(saw(92, d) * gate(n, 0.002, 0.012), 0.15), 5, 2), 0.24)

    # mounts: a deep drive "thunk"
    d = 0.14
    n, x = int(SR * d), t(d)
    thunk = np.sin(2 * np.pi * np.cumsum(np.linspace(72, 36, n)) / SR) * np.exp(-x / 0.05)
    B["thunk"] = norm(thunk + 0.35 * lowpass(rng.standard_normal(n), 0.25) * np.exp(-x / 0.003), 0.48)

    # [ OK ]: a two-note FM bip-bop that climbs the scale through the boot (8 steps, 220-555 Hz)
    B["ok"] = []
    for semis in (0, 2, 4, 7, 9, 12, 14, 16):
        f = 220 * 2 ** (semis / 12)
        parts = []
        for off, ff in ((0.0, f), (0.024, f * 1.5)):
            d = 0.024
            n = int(SR * d)
            note = (fm(ff, 1.0, 1.6, d) + 0.5 * sine(ff / 2, d)) * gate(n, 0.001, 0.007)
            parts.append((off, note))
        B["ok"].append(norm(crush(mix(0.06, parts), 6, 2), 0.28))

    # spinner frame: a low pulsing whirr
    d = 0.07
    n, x = int(SR * d), t(0.07)
    B["whirr"] = norm(crush(lowpass(saw(64, d) * (0.6 + 0.4 * np.sin(2 * np.pi * 40 * x)) * gate(n, 0.003, 0.02), 0.08), 5, 3), 0.24)

    # memory-test ticks, rising
    B["mem"] = []
    for i in range(8):
        d = 0.022
        n = int(SR * d)
        B["mem"].append(norm(lowpass(square(130 * 2 ** (i / 8), d, 0.25) * gate(n, 0.001, 0.006), 0.45), 0.20))

    # progress-bar steps: a square tone climbing from 98 Hz, one per step, with a sub layer
    B["step"] = []
    for i in range(26):
        f = 98 * 2 ** (i / 12)
        d = 0.03
        n = int(SR * d)
        B["step"].append(norm(crush((square(f, d, 0.25) + 0.5 * sine(f / 2, d)) * gate(n, 0.001, 0.008), 6, 2), 0.26))

    # section headers and loader lines
    B["hdr"] = norm(crush(mix(0.12, [(0.0, square(220, 0.04) * gate(int(SR * 0.04), 0.001, 0.008)),
                                     (0.05, square(330, 0.05) * gate(int(SR * 0.05), 0.001, 0.01))]), 6, 2), 0.22)

    # firmware POST: two beeps an octave-ish lower than a PC speaker, with a sub layer
    a = square(440, 0.07) * gate(int(SR * 0.07), 0.001, 0.008)
    b = square(660, 0.10) * gate(int(SR * 0.10), 0.001, 0.012)
    sub = mix(0.21, [(0.0, sine(220, 0.07) * 0.6 * gate(int(SR * 0.07), 0.001, 0.008)),
                     (0.09, sine(330, 0.10) * 0.6 * gate(int(SR * 0.10), 0.001, 0.012))])
    B["post"] = norm(crush(mix(0.21, [(0.0, a), (0.09, b)]) + sub, 6, 2), 0.34)

    # "Welcome to Arch Linux!": a deep boom swelling in
    d = 0.75
    n, x = int(SR * d), t(0.75)
    envl = np.minimum(x / 0.05, 1) * np.exp(-x / 0.3)
    boom = (sine(46, d) + 0.5 * sine(92, d) + 0.25 * lowpass(rng.standard_normal(n), 0.05)) * envl
    B["boom"] = norm(boom, 0.5)
    return B


def build_ready():
    """The 'system ready' sound: three rising digital notes, a sub boom, and a deep ring-modulated robotic hold."""
    parts = []
    for start, f in ((0.0, 196.0), (0.08, 261.6), (0.16, 392.0)):
        d = 0.08
        n = int(SR * d)
        parts.append((start, (square(f, d) * 0.6 + fm(f, 2.0, 1.4, d) * 0.4) * gate(n, 0.001, 0.02)))
    d = 0.95
    x = t(d)
    boom = sine(65, d) * np.exp(-x / 0.35) * gate(int(SR * d), 0.004, 0.08)
    parts.append((0.0, boom * 0.9))
    hold_d = 0.75
    hx = t(hold_d)
    hold = (saw(196.0, hold_d) * 0.5 + square(98.0, hold_d, 0.25) * 0.4) * np.sin(2 * np.pi * 30 * hx)   # ring-mod: the robot voice
    hold = hold * np.exp(-hx / 0.28) * gate(len(hold), 0.002, 0.06)
    parts.append((0.22, hold))
    return norm(crush(mix(1.1, parts), 7, 2), 0.34)


# ------------------------------------------------------------------ live engine
class Engine:
    """Mixes sounds into one stream and feeds it to pw-cat in real time. play() returns immediately.
    The pipe is shrunk to 4 KB so audio never queues up: what you hear is what was just requested."""

    def __init__(self, enabled=True):
        self.on = False
        self.chunks = 0
        self.events = []
        if not enabled or not shutil.which("pw-cat"):
            return
        try:
            self.bank = build_bank()
            self.proc = subprocess.Popen(
                ["pw-cat", "-p", "--raw", "--format", "s16", "--rate", str(SR), "--channels", "1", "--latency", "30ms", "-"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                fcntl.fcntl(self.proc.stdin.fileno(), F_SETPIPE_SZ, 4096)
            except OSError:
                pass
        except Exception:
            return
        self.lock = threading.Lock()
        self.buf = np.zeros(0)
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()
        self.on = True

    def wait_ready(self, timeout=1.0):
        """Block until PipeWire is actually consuming audio, so the first sounds aren't delayed."""
        end = time.time() + timeout
        while self.on and self.chunks < 14 and time.time() < end:
            time.sleep(0.01)

    def play(self, name, i=0, gain=1.0, semis=0.0):
        """semis: shift the sound up by this many semitones (plain resampling: higher and a little shorter)."""
        if not self.on:
            return
        clip = self.bank.get(name)
        if clip is None:
            return
        if isinstance(clip, list):
            clip = clip[i % len(clip)]
        if semis:
            rate = 2 ** (semis / 12)
            clip = np.interp(np.arange(0, len(clip) - 1, rate), np.arange(len(clip)), clip)
        self.events.append((time.time(), name, i))
        with self.lock:
            if len(self.buf) < len(clip):
                self.buf = np.concatenate([self.buf, np.zeros(len(clip) - len(self.buf))])
            self.buf[: len(clip)] += clip * gain

    def _run(self):
        n = 441                      # 10 ms per chunk
        while self.running:
            with self.lock:
                chunk, self.buf = self.buf[:n], self.buf[n:]
            if len(chunk) < n:
                chunk = np.pad(chunk, (0, n - len(chunk)))
            pcm = (np.tanh(chunk * 1.1) * 0.95 * 32767).astype("<i2").tobytes()
            try:
                self.proc.stdin.write(pcm)
                self.proc.stdin.flush()
            except Exception:
                break
            self.chunks += 1

    def stop(self):
        self.running = False
        if self.on:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            try:
                self.proc.terminate()
            except Exception:
                pass
