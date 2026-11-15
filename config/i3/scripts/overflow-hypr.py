#!/usr/bin/env python3
"""Hyprland version of overflow-ws.py: a new window opened on the dashboard workspace (1) gets its own fresh workspace;
when the workspace you are on empties (its last window closes) you return to workspace 1. Runs in the background (started from hyprland.lua). One instance only."""
import fcntl, json, os, re, socket, subprocess, sys, time

HOME_WS = "1"
EXEMPT = re.compile(r"^(dash-|chesscom$|[Zz]enity$|bootsplash$|dropterm$|Spotify$|spotify$|spotui$|bttui$|cavaterm$)")
CANDIDATES = [2, 3, 4, 5, 6, 7, 8, 10]      # lowest free one is used (1 = dashboard, 9 = Spotify are skipped)

lock = open("/tmp/overflow-hypr.lock", "w")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(0)

mine = set()


def hl(expr):
    return subprocess.run(["hyprctl", "dispatch", expr], capture_output=True, text=True).stdout


def jq(*args):
    try:
        return json.loads(subprocess.run(["hyprctl", *args, "-j"], capture_output=True, text=True).stdout)
    except Exception:
        return []


def busy_workspaces():
    return {w["name"] for w in jq("workspaces") if w.get("windows", 0) > 0} | {w["name"] for w in jq("monitors") for w in [w["activeWorkspace"]]}


def pick():
    busy = busy_workspaces() | mine
    for n in CANDIDATES:
        if str(n) not in busy:
            return str(n)
    n = 11
    while str(n) in busy:
        n += 1
    return str(n)


def on_open(addr, ws, cls):
    if ws != HOME_WS or not cls or EXEMPT.match(cls):
        return
    target = pick()
    hl(f'hl.dsp.window.move({{ workspace = "{target}", window = "address:0x{addr}", follow = true }})')
    mine.add(target)


def on_close():
    """When the last window on the workspace you are on closes, go back to workspace 1 (any workspace, not only the ones made here)."""
    time.sleep(0.2)
    wins = {}
    for c in jq("clients"):
        wins[c["workspace"]["name"]] = wins.get(c["workspace"]["name"], 0) + 1
    aw = jq("activeworkspace")
    active = aw.get("name") if isinstance(aw, dict) else None
    for name in list(mine):
        if wins.get(name, 0) == 0:
            mine.discard(name)
    if active and active != HOME_WS and not active.startswith("special:") and wins.get(active, 0) == 0:
        hl(f'hl.dsp.focus({{ workspace = {HOME_WS} }})')


def main():
    path = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket2.sock"
    while True:
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(path)
            buf = b""
            while True:
                data = s.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    ev, _, rest = line.decode(errors="replace").partition(">>")
                    if ev == "openwindow":
                        addr, ws, cls, _title = (rest.split(",", 3) + ["", "", "", ""])[:4]
                        on_open(addr, ws, cls)
                    elif ev == "closewindow":
                        on_close()
        except Exception:
            pass
        time.sleep(1)


if __name__ == "__main__":
    main()
