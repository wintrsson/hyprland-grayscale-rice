#!/usr/bin/env python3
"""Flicker helper for the boot sequence.

    glitch.py run PID   hide every dashboard window (and the bar) the moment it appears, and when
                        process PID (the splash) exits, flicker them all back in at random moments.
Uses picom's per-window opacity (_NET_WM_WINDOW_OPACITY), so no layout changes are involved."""
import os
import random
import subprocess
import sys
import threading
import time


def find(pattern):
    out = subprocess.run(["xdotool", "search", "--class", pattern], capture_output=True, text=True).stdout
    return out.split()


def targets():
    return set(find("^dash-")) | set(find("^Polybar$"))


_frames = {}


def frame_of(wid):
    """picom reads opacity from the window i3 wraps around each client, not the client itself.
    Unframed windows (like the bar) are used directly."""
    if wid not in _frames:
        out = subprocess.run(["xwininfo", "-id", wid, "-tree"], capture_output=True, text=True).stdout
        frame = wid
        for line in out.splitlines():
            if "Parent window id:" in line:
                if "root window" not in line:
                    frame = line.split("Parent window id:")[1].split()[0]
                break
        _frames[wid] = frame
    return _frames[wid]


def set_opacity(wid, value):
    target = frame_of(wid)
    if value >= 1.0:
        subprocess.run(["xprop", "-id", target, "-remove", "_NET_WM_WINDOW_OPACITY"], capture_output=True)
    else:
        subprocess.run(
            ["xprop", "-id", target, "-f", "_NET_WM_WINDOW_OPACITY", "32c", "-set", "_NET_WM_WINDOW_OPACITY",
             str(int(max(value, 0.0) * 0xFFFFFFFF))],
            capture_output=True,
        )


def set_all(wids, value):
    ts = [threading.Thread(target=set_opacity, args=(w, value)) for w in wids]
    for t in ts:
        t.start()
    for t in ts:
        t.join()


def alive(pid):
    try:
        os.kill(pid, 0)
        # a finished-but-unreaped child still "exists"; treat zombies as gone
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split(")")[-1].split()[0] != "Z"
    except (ProcessLookupError, FileNotFoundError, PermissionError):
        return False


def flicker_in(wid):
    time.sleep(random.uniform(0.0, 0.3))  # each pane locks on at its own moment
    steps = random.randint(4, 6)
    for _ in range(steps):
        set_opacity(wid, random.choice([0.0, 0.0, 0.12, 0.35, 0.7, 1.0]))
        time.sleep(random.uniform(0.02, 0.06))
    set_opacity(wid, 1.0)


def main():
    pid = int(sys.argv[2])
    hidden = set()

    def sweep():
        for w in targets():
            if w not in hidden:
                set_opacity(w, 0.0)
                hidden.add(w)

    while alive(pid):
        sweep()
        time.sleep(0.05)
    sweep()

    for w in hidden:
        frame_of(w)   # warm the frame cache so the flash is simultaneous
    # everything flickers in together: same opacity on every pane and the bar at the same instant
    panes = sorted(hidden)
    open("/tmp/dash-art-glitch", "w").close()   # the album pane starts its stretch / slice glitch at the same moment
    for v in [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]:   # hard on/off cuts, no in-between brightness
        set_all(panes, v)
        time.sleep(random.uniform(0.04, 0.09))
    set_all(panes, 1.0)

    # aftershocks: the signal wobbles a few more times after everything is on screen
    for _ in range(3):
        time.sleep(random.uniform(0.1, 0.3))
        victims = random.sample(panes, k=min(len(panes), random.randint(1, 3)))
        for _ in range(random.randint(2, 3)):
            for w in victims:
                set_opacity(w, 0.0)
            time.sleep(random.uniform(0.02, 0.06))
            for w in victims:
                set_opacity(w, 1.0)
            time.sleep(random.uniform(0.02, 0.05))
    for w in panes:
        set_opacity(w, 1.0)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "run":
        main()
