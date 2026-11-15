#!/usr/bin/env python3
"""Audio visualizer that keeps moving when it's quiet.

  viz.py tui    full-screen bars (the dashboard pane and the Super+C window)
  viz.py bar    one line of block characters for polybar

It runs cava for the real audio. When cava reports silence (media stopped or paused, volume 0, muted) the bars
ease into a slow rolling wave after about 0.8 s, and snap back to the real music the moment sound returns.
Tuning knobs are at the top."""
import atexit
import math
import os
import random
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

# ---- tuning ----
SILENCE_LEVEL = 0.004          # cava bar value (0-1) at or below this counts as silence
SILENCE_AFTER = 0.8            # seconds of silence before the idle wave starts
FADE_IN = 1.2                  # time constant (s) for the idle wave fading in
FADE_OUT = 0.08                # time constant (s) for it disappearing when sound returns
IDLE_FLOOR, IDLE_SWING = 0.12, 0.42   # idle wave height: floor, plus how far it swells (fractions of full height)
IDLE_SPEED = 0.7               # how fast the wave rolls (rad/s)

GRADIENT = [(0x4A, 0x4A, 0x4A), (0x7A, 0x7A, 0x7A), (0xAA, 0xAA, 0xAA), (0xD0, 0xD0, 0xD0), (0xFF, 0xFF, 0xFF)]
EIGHTHS = " ▁▂▃▄▅▆▇█"
BAR_W, GAP = 2, 1
TUI_MONO = True                # one spectrum across the whole width (bass on the left, treble on the right), not a mirrored stereo pair
TUI_RELEASE = 1.5              # how fast bars fall (full heights per second); every bar gets its own speed, 0.6x to 1.5x of this
TUI_CAPS = False               # True = little caps that hover above each bar, then drift down (removed: looked too floaty)
PEAK_HOLD, PEAK_FALL = 0.30, 0.55
TUI_TILT = 0.7                 # extra gain toward the left/right edges (the quiet high frequencies): 0 = off, edges get 1 + this times the gain of the middle
TUI_NOISE = 8                  # cava noise_reduction for the big visualizer: lower = snappier and jumpier (was 25)


def idle_value(i, n, t):
    """A smooth traveling wave with a slow swell on top, for bar i of n at time t."""
    x = i / (n - 1) if n > 1 else 0.0
    roll = 0.5 + 0.5 * math.sin(IDLE_SPEED * t - 3.4 * x)
    swell = 0.5 + 0.5 * math.sin(0.27 * t + 2.2 * x + 1.3)
    return IDLE_FLOOR + IDLE_SWING * roll * (0.55 + 0.45 * swell)


class Source:
    """Yields lists of bar heights (0-1): real audio from cava, blended with the idle wave during silence."""

    def __init__(self, bars, fps, noise, tilt=0.0, mono=False):
        self.mono = mono
        self.bars, self.fps, self.noise, self.tilt = (bars if mono else bars + (bars % 2)), fps, noise, tilt      # stereo needs an even number of bars
        self.proc = None
        self.silent_for, self.s, self.last = SILENCE_AFTER, 1.0, time.time()   # start in the idle wave: bars are visible from the very first frame, real audio takes over the moment it arrives
        atexit.register(self.close)
        self.start()

    def start(self):
        self.close()
        cfg = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False)
        cfg.write(f"[general]\nbars = {self.bars}\nframerate = {self.fps}\nlower_cutoff_freq = 80\n[input]\nmethod = pulse\nsource = auto\n"
                  f"[output]\nchannels = {'mono' if self.mono else 'stereo'}\nmethod = raw\nraw_target = /dev/stdout\ndata_format = ascii\nascii_max_range = 1000\n"
                  f"bar_delimiter = 59\nframe_delimiter = 10\n[smoothing]\nnoise_reduction = {self.noise}\n")
        cfg.close()
        self.cfg = cfg.name
        self.proc = subprocess.Popen(["cava", "-p", cfg.name], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None
        try:
            os.unlink(self.cfg)
        except Exception:
            pass

    def frame(self):
        """Block for the next frame (or fall back to silence if cava goes quiet) and return the blended heights."""
        real = [0.0] * self.bars
        ready = select.select([self.proc.stdout], [], [], 2.5 / self.fps)[0]
        if ready:
            line = self.proc.stdout.readline()
            if not line:
                self.start()
            else:
                try:
                    vals = [int(v) / 1000.0 for v in line.strip().split(";") if v != ""]
                    if len(vals) == self.bars:
                        real = vals
                        if self.tilt and self.mono:                 # treble carries less energy: lift it toward the right
                            real = [min(1.0, v * (1 + self.tilt * i / max(self.bars - 1, 1))) for i, v in enumerate(vals)]
                        elif self.tilt:
                            mid = (self.bars - 1) / 2
                            real = [min(1.0, v * (1 + self.tilt * abs(i - mid) / mid)) for i, v in enumerate(vals)]
                except ValueError:
                    pass
        now = time.time()
        dt = min(now - self.last, 0.25)
        self.last = now
        self.silent_for = self.silent_for + dt if max(real) <= SILENCE_LEVEL else 0.0
        target = 1.0 if self.silent_for >= SILENCE_AFTER else 0.0
        tau = FADE_IN if target > self.s else FADE_OUT
        self.s += (target - self.s) * (1 - math.exp(-dt / tau))
        if self.s < 0.002:
            self.s = 0.0
            return real
        return [r * (1 - self.s) + idle_value(i, self.bars, now) * self.s for i, r in enumerate(real)]


# ------------------------------------------------------------------ polybar mode
def run_bar():
    src = Source(4, 30, 30)
    levels = "▁▂▃▄▅▆▇█"
    while True:
        v = src.frame()
        sys.stdout.write("".join(levels[max(0, min(7, int(x * 8)))] for x in v) + "\n")
        sys.stdout.flush()


# ------------------------------------------------------------------ full-screen mode
def gradient_color(frac):
    f = max(0.0, min(1.0, frac)) * (len(GRADIENT) - 1)
    i = min(int(f), len(GRADIENT) - 2)
    a, b, k = GRADIENT[i], GRADIENT[i + 1], f - i
    return "\033[38;2;%d;%d;%dm" % tuple(int(a[c] + (b[c] - a[c]) * k) for c in range(3))


def bars_for(cols):
    n = max(2, (cols + GAP) // (BAR_W + GAP))
    return n - (n % 2)


def run_tui():
    sys.stdout.write("\033[?1049h\033[?25l\033[2J")
    atexit.register(lambda: sys.stdout.write("\033[?25h\033[?1049l"))
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    size = shutil.get_terminal_size((100, 30))
    src = Source(bars_for(size.columns), 60, TUI_NOISE, TUI_TILT, TUI_MONO)
    hs = pk = hold = decay = None
    last = time.time()
    while True:
        v = src.frame()
        size = shutil.get_terminal_size((100, 30))
        if bars_for(size.columns) != src.bars:
            src = Source(bars_for(size.columns), 60, TUI_NOISE, TUI_TILT, TUI_MONO)          # window was resized: new bar count
            hs = None
            continue
        now = time.time(); dt = min(now - last, 0.1); last = now
        if hs is None or len(hs) != len(v):
            rnd = random.Random(7)
            hs, pk, hold = [0.0] * len(v), [0.0] * len(v), [0.0] * len(v)
            decay = [rnd.uniform(0.6, 1.5) for _ in v]                 # each bar falls at its own speed: no two behave alike
        for i, h in enumerate(v):
            hs[i] = h if h >= hs[i] else max(h, hs[i] - TUI_RELEASE * decay[i] * dt)
            if hs[i] >= pk[i]:
                pk[i], hold[i] = hs[i], PEAK_HOLD
            elif hold[i] > 0:
                hold[i] -= dt
            else:
                pk[i] = max(hs[i], pk[i] - PEAK_FALL * dt)
        cols, rows = size.columns, max(size.lines, 2)
        pitch = BAR_W + GAP
        left = max(0, (cols - (src.bars * pitch - GAP)) // 2)
        caps = [min(rows, math.ceil(p * rows)) for p in pk]
        tops = [math.ceil(h * rows) for h in hs]
        out = []
        for r in range(rows):
            top = rows - r                                         # this row covers heights (top-1, top] of the pane
            cells = []
            for k, h in enumerate(hs):
                filled = h * rows
                if filled >= top:
                    ch = "█"
                elif filled > top - 1:
                    ch = EIGHTHS[max(1, int((filled - (top - 1)) * 8))]
                elif TUI_CAPS and caps[k] == top and caps[k] > tops[k] + 1 and pk[k] > 0.02:
                    ch = "▄"                                       # the hovering peak cap
                else:
                    ch = " "
                cells.append(ch * BAR_W + " " * GAP)
            out.append(gradient_color(1 - r / max(rows - 1, 1)) + " " * left + "".join(cells).rstrip(" "))
        sys.stdout.write("\033[H" + "\n".join(o + "\033[K" for o in out))
        sys.stdout.flush()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "tui"
    try:
        run_bar() if mode == "bar" else run_tui()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
