#!/usr/bin/env python3
"""Boot splash that looks like a real boot, built from real data on this machine:
firmware/hardware line, kernel messages from THIS boot, systemd-style [ OK ] lines for the services and mounts
that are actually running, then the dashboard's own system checks. Monochrome. Any key skips it.
Speed: BOOT_SPEED=2 plays it twice as fast, BOOT_SPEED=0.5 half speed."""
import os
import platform
import random
import collections
import re
import select
import shutil
import subprocess
import sys
import termios
import threading
import time
import tty
import zlib

ESC = "\033"
RESET = f"{ESC}[0m"
BOLD = f"{ESC}[1m"
SPEED = float(os.environ.get("BOOT_SPEED", "1") or 1)

# ---- sound (synthesized clips in ~/.config/i3/sounds; disable with BOOT_SOUND=0 or `touch ~/.config/i3/no-boot-sound`) ----
SOUND_DIR = os.path.expanduser("~/.config/i3/sounds")
SOUND_ON = os.environ.get("BOOT_SOUND", "1") != "0" and not os.path.exists(os.path.expanduser("~/.config/i3/no-boot-sound"))
PLAYER = next((p for p in ("pw-play", "paplay", "aplay") if shutil.which(p)), None)
_playing = []


def play(name):
    """Fire-and-forget: never blocks the animation, and a missing file or player is simply silent."""
    if not (SOUND_ON and PLAYER):
        return
    path = os.path.join(SOUND_DIR, name + ".wav")
    if not os.path.exists(path):
        return
    try:
        _playing.append(subprocess.Popen([PLAYER, path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, start_new_session=True))
    except Exception:
        pass


try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bootsynth import Engine
except Exception:          # no synth available: stay silent rather than fail
    class Engine:
        def __init__(self, *a, **k):
            self.on = False
            self.events = []

        def play(self, *a, **k):
            pass

        def wait_ready(self, *a, **k):
            pass

        def stop(self):
            pass

ENGINE = None
PITCH_RANGE = 16.0          # semitones the per-line sounds climb over the whole boot, up to the loading bar
PITCH = 0.0                 # current climb (semitones); set from how far through the boot we are
LINE_SOUNDS = ("tick", "thud", "buzz", "thunk", "ok")


def set_pitch(progress):
    """progress 0..1 through the boot lines (kernel log, mounts, services, checks) -> pitch of every line sound."""
    global PITCH
    PITCH = PITCH_RANGE * max(0.0, min(1.0, progress))


def ev(name, i=0, gain=1.0):
    """Trigger a live sound at this exact moment (no-op when sound is off)."""
    if ENGINE is not None:
        ENGINE.play(name, i, gain, semis=PITCH if name in LINE_SOUNDS else 0.0)


def stop_sounds():
    for pr in _playing:
        try:
            if pr.poll() is None:
                pr.terminate()
        except Exception:
            pass



def gray(n):  # 0 (dark) .. 23 (white)
    return f"{ESC}[38;5;{232 + max(0, min(23, n))}m"


def run(cmd, timeout=6):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def read(path):
    try:
        return open(path).read().strip()
    except Exception:
        return ""


# ------------------------------------------------------------------ real data, gathered in the background
D = {}


# kernel lines that mention IP addresses, MAC addresses, serial numbers or UUIDs are left out of the on-screen log
PRIVATE = re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b|([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|SerialNumber|serial|UUID", re.I)


def gather():
    D["vendor"] = read("/sys/class/dmi/id/sys_vendor")
    D["product"] = read("/sys/class/dmi/id/product_name")
    D["bios"] = read("/sys/class/dmi/id/bios_version")
    D["bios_date"] = read("/sys/class/dmi/id/bios_date")
    D["cpu"] = next((l.split(":", 1)[1].strip() for l in run(["lscpu"]).splitlines() if l.startswith("Model name")), "")
    D["threads"] = os.cpu_count() or 1
    try:
        D["mem_mb"] = int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal"))) // 1024
    except Exception:
        D["mem_mb"] = 0
    D["kernel"] = platform.release()

    # kernel log from this boot, hostname stripped so it reads like dmesg
    ks = []
    for l in run(["journalctl", "-k", "-b", "-o", "short-monotonic", "--no-pager", "-q"], 10).splitlines():
        l = re.sub(r"^(\[[^\]]+\]) \S+ kernel: ", r"\1 ", l)
        if l.startswith("[") and "Command line" not in l and not PRIVATE.search(l):
            ks.append(l)
    D["klog"] = ks

    # running services -> "Started <description>."
    units = []
    for l in run(["systemctl", "list-units", "--type=service", "--state=running", "--plain", "--no-legend", "--no-pager"]).splitlines():
        parts = l.split(None, 4)
        if len(parts) == 5 and "@" not in parts[0]:
            units.append(parts[4].strip())
    D["units"] = units

    # active targets -> "Reached target <description>."
    tg = []
    for l in run(["systemctl", "list-units", "--type=target", "--state=active", "--plain", "--no-legend", "--no-pager"]).splitlines():
        parts = l.split(None, 4)
        if len(parts) == 5:
            tg.append(parts[4].strip())
    D["targets"] = tg

    # real mounts
    mounts = []
    for l in run(["findmnt", "-rn", "-o", "TARGET,FSTYPE"]).splitlines():
        t, _, fs = l.partition(" ")
        if t.startswith(("/proc", "/sys", "/dev", "/run", "/tmp")) or fs in ("overlay", "autofs") or len(t) > 36:
            continue
        mounts.append(t)
    D["mounts"] = mounts

    # dashboard checks
    f = {}
    for l in run(["xrandr", "--current"]).splitlines():
        if " connected" in l:
            res = re.search(r"(\d+x\d+)\+", l)
            f["display"] = f"{l.split()[0]}  {res.group(1) if res else ''}".strip()
            break
    f["compositor"] = "picom  blur on" if run(["pgrep", "-x", "picom"]).strip() else "off"
    f["audio"] = "pipewire" if "PipeWire" in run(["pactl", "info"]) else "ready"
    f["visualizer"] = "cava  armed" if shutil.which("cava") else "missing"
    st = run(["docker", "ps", "-a", "--format", "{{.State}}"]).split()
    if st:
        f["containers"] = f"{st.count('running')}/{len(st)} up"
    ts = [l for l in run(["tailscale", "status"]).splitlines() if l[:1].isdigit()]
    if ts:
        f["tailscale"] = f"{sum('offline' not in l for l in ts)}/{len(ts)} online"
    try:
        du = shutil.disk_usage("/")
        f["disk"] = f"{du.used // 2**30}/{du.total // 2**30} GiB"
    except Exception:
        pass
    D["checks"] = f
    D["ready"] = True


threading.Thread(target=gather, daemon=True).start()


# ------------------------------------------------------------------ output helpers
class Skip(Exception):
    pass


def pause(seconds):
    """Sleep (scaled by BOOT_SPEED); any key press aborts the whole splash."""
    end = time.time() + seconds / SPEED
    while True:
        if select.select([sys.stdin], [], [], 0)[0]:
            raise Skip
        left = end - time.time()
        if left <= 0:
            return
        time.sleep(min(left, 0.02))


def width():
    return shutil.get_terminal_size((160, 45)).columns


def out(text=""):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def cut(s, n=None):
    n = n or width() - 2
    return s if len(s) <= n else s[: n - 1] + "…"


def ok(text, tag="  OK  "):
    out(f"{gray(11)}[{RESET}{BOLD}{gray(23)}{tag}{RESET}{gray(11)}]{RESET} {gray(18)}{cut(text, width() - 12)}{RESET}")


def spinner(text, frames=7):
    """A 'start job is running' line that spins, then resolves to OK."""
    for i in range(frames):
        pos = i % 4
        cells = ["*" if p == (pos if pos < 3 else 6 - pos - 1) else " " for p in range(4)]
        sys.stdout.write(f"\r{ESC}[2K{gray(11)}[{RESET}{gray(23)}{''.join(cells)}{RESET}{gray(11)}]{RESET} {gray(16)}A start job is running for {cut(text, width() - 60)} ({i // 2 + 1}s / no limit){RESET}")
        sys.stdout.flush()
        ev("whirr")
        pause(0.07)
    sys.stdout.write(f"\r{ESC}[2K")
    sys.stdout.flush()


def wait_for(key, timeout=4.0):
    t = time.time()
    while key not in D and time.time() - t < timeout:
        pause(0.02)


# ------------------------------------------------------------------ the show (every sound is tied to what appears)
def post():
    pause(0.25)
    ENGINE.wait_ready(1.0)            # don't start until PipeWire is really consuming audio
    wait_for("product")
    out(f"{gray(23)}{BOLD}{D.get('vendor', '')}{RESET} {gray(21)}{D.get('product', '')}{RESET}")
    ev("hdr")
    out(f"{gray(14)}BIOS {D.get('bios', '')}   {D.get('bios_date', '')}{RESET}")
    pause(0.12)
    out()
    cpu = D.get("cpu", "")
    out(f"{gray(18)}{cpu}   {D.get('threads', '')} threads{RESET}")
    ev("hdr")
    total = D.get("mem_mb", 0) or 16384
    step = max(total // 40, 1)
    for k, mb in enumerate(range(0, total, step)):
        sys.stdout.write(f"\r{gray(16)}Memory test: {mb:>6} MB{RESET}")
        sys.stdout.flush()
        if k % 2 == 0:
            ev("mem", k // 2)
        pause(0.008)
    sys.stdout.write(f"\r{gray(16)}Memory test: {total:>6} MB   {gray(23)}OK{RESET}\n")
    ev("post")
    out()
    pause(0.2)
    out(f"{gray(16)}Loading Linux {D.get('kernel', '')} ...{RESET}")
    ev("hdr")
    pause(0.18)
    out(f"{gray(16)}Loading initial ramdisk ...{RESET}")
    ev("thunk")
    pause(0.16)
    ev("thunk", gain=0.7)
    pause(0.14)
    out()


def kernel_log():
    wait_for("klog")
    lines = D.get("klog", [])
    if not lines:
        return
    keep = 150
    if len(lines) > keep:
        idx = sorted(set(list(range(10)) + [int(i * (len(lines) - 1) / (keep - 1)) for i in range(keep)] + list(range(len(lines) - 6, len(lines)))))
        lines = [lines[i] for i in idx]
    for n, l in enumerate(lines):
        set_pitch(0.60 * n / max(len(lines) - 1, 1))
        loud = re.search(r"error|fail|warn|bug", l, re.I)
        out(f"{gray(23 if loud else 15)}{cut(l)}{RESET}")
        if loud:
            ev("buzz")                                   # errors and warnings growl
        elif n % 14 == 0:
            ev("thud")                                   # a heavy beat every so often
        else:
            ev("tick", 2)                                # every line is one step higher than the last (see set_pitch)
        d = 0.003 + (0.02 * max(0, n - len(lines) + 25) / 25)
        if random.random() < 0.025:
            d += random.uniform(0.05, 0.14)
        pause(d)
    pause(0.15)


def systemd_phase():
    out()
    out(f"{gray(22)}Welcome to {BOLD}Arch Linux{RESET}{gray(22)}!{RESET}")
    ev("boom")
    out()
    pause(0.3)
    mounts = D.get("mounts", [])[:8]
    units_all = D.get("units", [])
    targets_all = [t for t in D.get("targets", []) if "Graphical" not in t][:10]
    total_lines = max(len(mounts) + len(units_all) + len(targets_all), 1)
    done = 0
    for m in mounts:
        set_pitch(0.60 + 0.30 * done / total_lines); done += 1
        ok(f"Mounted {m}.")
        ev("thunk")
        pause(random.choice([0.03, 0.045, 0.06, 0.08]))
    units = D.get("units", [])
    slow = set(random.sample(range(len(units)), k=min(2, len(units)))) if units else set()
    for i, u in enumerate(units):
        if i in slow:
            spinner(u)
        set_pitch(0.60 + 0.30 * done / total_lines); done += 1
        ok(f"Started {u}.")
        ev("ok", 0)                                      # the pitch climbs as the system comes up (see set_pitch)
        pause(random.choice([0.025, 0.035, 0.05, 0.07]))
    targets = [t for t in D.get("targets", []) if "Graphical" not in t]
    for j, tg in enumerate(targets[:10]):
        set_pitch(0.60 + 0.30 * done / total_lines); done += 1
        ok(f"Reached target {tg}.")
        ev("ok", 0)
        pause(random.choice([0.03, 0.05, 0.07]))
    pause(0.1)


def checks_phase():
    out()
    out(f"{gray(22)}{BOLD}tephra-init{RESET}{gray(14)}  dashboard subsystems{RESET}")
    ev("hdr")
    n = 0
    for label, key in [("display", "display"), ("compositor", "compositor"), ("audio bus", "audio"), ("visualizer", "visualizer"),
                       ("containers", "containers"), ("tailscale", "tailscale"), ("root volume", "disk")]:
        v = D.get("checks", {}).get(key)
        if v:
            set_pitch(0.90 + 0.10 * n / 7)
            ok(f"{label:<12} {gray(23)}{v}{RESET}")
            ev("ok", 0)
            n += 1
            pause(random.choice([0.07, 0.1, 0.14]))
    out()
    bar_w = max(20, min(60, width() - 24))
    for k, pct in enumerate(range(0, 101, 4)):
        fill = int(pct / 100 * bar_w)
        sys.stdout.write(f"\r{gray(16)}Starting dashboard {gray(12)}[{gray(23)}{'█' * fill}{gray(8)}{'░' * (bar_w - fill)}{gray(12)}]{gray(18)} {pct:3d}%{RESET}")
        sys.stdout.flush()
        ev("step", k)                                    # one rising tone per step of the bar
        pause(random.choice([0.025, 0.035, 0.045]))
    out()
    play("ready")                                        # rendered file: finishes playing after the window closes
    graphical = next((t for t in D.get("targets", []) if "Graphical" in t), "Graphical Interface")
    ok(f"Reached target {graphical}.")
    pause(0.35)


AV_DELAY = float(os.environ.get("BOOT_AV_DELAY", "0.10"))   # seconds the picture is held back so it lands with the sound


class DelayedOut:
    """Wraps stdout: everything written appears AV_DELAY later (sound is instant, picture is held), keeping order."""

    def __init__(self, real, delay):
        self.real, self.delay = real, delay
        self.q = collections.deque()
        self.lock = threading.Lock()
        self.alive = True
        threading.Thread(target=self._loop, daemon=True).start()

    def write(self, text):
        with self.lock:
            self.q.append((time.time() + self.delay, text))
        return len(text)

    def flush(self):
        pass

    def fileno(self):
        return self.real.fileno()

    def _loop(self):
        while self.alive or self.q:
            wrote = False
            while True:
                with self.lock:
                    due = self.q[0][1] if self.q and self.q[0][0] <= time.time() else None
                    if due is not None:
                        self.q.popleft()
                if due is None:
                    break
                self.real.write(due)
                wrote = True
            if wrote:
                self.real.flush()
            time.sleep(0.002)

    def drain(self, timeout=1.0):
        end = time.time() + timeout
        while self.q and time.time() < end:
            time.sleep(0.01)
        self.alive = False


def main():
    global ENGINE
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sys.stdout.write(f"{ESC}[?1049h{ESC}[?25l{ESC}[2J{ESC}[H")
    ENGINE = Engine(SOUND_ON)
    real_out = sys.stdout
    delayed = None
    if getattr(ENGINE, "on", False) and AV_DELAY > 0:
        delayed = sys.stdout = DelayedOut(real_out, AV_DELAY)
    try:
        tty.setcbreak(fd)
        for step in (post, kernel_log, systemd_phase, checks_phase):
            step()
        sys.stdout.write(f"{ESC}[2J{ESC}[H")
        pause(0.08)
    except Skip:
        stop_sounds()
    finally:
        log = os.environ.get("BOOT_EVENT_LOG")
        if log:
            try:
                with open(log, "w") as f:
                    for ts, name, i in ENGINE.events:
                        f.write(f"{ts:.3f} {name} {i}\n")
            except Exception:
                pass
        ENGINE.stop()
        if delayed is not None:
            delayed.drain()
            sys.stdout = real_out
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write(f"{ESC}[?25h{ESC}[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
