#!/usr/bin/env python3
"""New windows opened while you're on the dashboard workspace get their own fresh workspace.
When the last window on such a workspace closes, you're taken back to workspace 1.

Runs in the background (started from ~/.config/i3/config). One instance only."""
import fcntl
import json
import re
import subprocess
import sys
import time

HOME_WS = "1"                 # where you return to
DASH_WS = "1"                 # the dashboard workspace (also where you return to)
EXEMPT = re.compile(r"^(dash-|chesscom$|[Zz]enity$|bootsplash$|dropterm$|Spotify$|Polybar$)")
CANDIDATES = [2, 3, 4, 5, 6, 7, 8, 10]   # lowest free one is used (1 = dashboard, 9 = Spotify are skipped)

lock = open("/tmp/overflow-ws.lock", "w")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(0)            # already running

mine = set()               # workspaces this helper created


def i3(*args):
    return subprocess.run(["i3-msg", *args], capture_output=True, text=True).stdout


def tree():
    return json.loads(i3("-t", "get_tree"))


def workspace_of(node, con_id, ws=None):
    """Name of the workspace that holds container con_id, or None."""
    if node.get("type") == "workspace":
        ws = node.get("name")
    if node.get("id") == con_id:
        return ws
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = workspace_of(child, con_id, ws)
        if found is not None:
            return found
    return None


def window_count(node, ws_name, inside=False):
    if node.get("type") == "workspace":
        inside = node.get("name") == ws_name
    n = 1 if (inside and node.get("window")) else 0
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        n += window_count(child, ws_name, inside)
    return n


def workspaces():
    return json.loads(i3("-t", "get_workspaces"))


def pick_workspace():
    existing = {w["name"] for w in workspaces()}
    for n in CANDIDATES:
        if str(n) not in existing:
            return str(n)
    n = 11
    while str(n) in existing:
        n += 1
    return str(n)


def on_new(container):
    props = container.get("window_properties") or {}
    cls = props.get("class") or ""
    if not cls or EXEMPT.match(cls):
        return
    con_id = container["id"]
    ws = None
    for _ in range(10):                      # the tree needs a moment to catch up
        ws = workspace_of(tree(), con_id)
        if ws is not None:
            break
        time.sleep(0.03)
    if ws != DASH_WS:
        return
    target = pick_workspace()
    i3(f"[con_id={con_id}] move container to workspace number {target}")
    i3(f"workspace number {target}")
    i3(f"[con_id={con_id}] focus")
    mine.add(target)


def on_close():
    time.sleep(0.15)
    t = tree()
    focused = next((w["name"] for w in workspaces() if w["focused"]), None)
    for name in list(mine):
        if window_count(t, name) == 0:
            mine.discard(name)
            if focused == name:
                i3(f"workspace number {HOME_WS}")


def main():
    while True:
        proc = subprocess.Popen(["i3-msg", "-t", "subscribe", "-m", '["window"]'],
                                stdout=subprocess.PIPE, text=True)
        for line in proc.stdout:
            try:
                ev = json.loads(line)
                if ev.get("change") == "new":
                    on_new(ev["container"])
                elif ev.get("change") == "close":
                    on_close()
            except Exception:
                pass
        time.sleep(1)       # i3 restarted or the stream dropped: reconnect


if __name__ == "__main__":
    main()
