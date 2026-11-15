#!/usr/bin/env python3
"""Remember your terminals and bring them back after a reboot.

  term-session.py auto      at login: reopen the saved terminals, then keep saving every 20 s (used by the boot script)
  term-session.py save      save right now
  term-session.py restore   reopen the saved terminals right now
  term-session.py status    show what is saved

What is saved for each ordinary terminal window (class "Alacritty"): its workspace (or scratchpad), its folder, and, if
Claude Code was running in it, which conversation, so it reopens with `claude --resume <id>`.
Not saved: the scrollback text, or programs other than Claude. Turn automatic reopening off: touch ~/.config/i3/no-terminal-restore"""
import collections
import fcntl
import glob
import json
import os
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
STATE = f"{HOME}/.config/i3/terminal-session.json"
FLAG = f"{HOME}/.config/i3/no-terminal-restore"
PROJECTS = f"{HOME}/.claude/projects"
HYPR = bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
STAGE_WS = "8"                      # scratchpad terminals are opened here first, then hidden


def run(*cmd):
    return subprocess.run(list(cmd), capture_output=True, text=True).stdout


def i3(cmd):
    """i3 commands; under Hyprland the few commands used here are translated."""
    if HYPR:
        import re
        m = re.match(r"workspace number (\S+)", cmd)
        if m:
            return run("hyprctl", "dispatch", f"hl.dsp.focus({{ workspace = {m.group(1)} }})")
        m = re.match(r"\[id=(\S+)\] move scratchpad", cmd)
        if m:
            return run("hyprctl", "dispatch", f'hl.dsp.window.move({{ workspace = "special:hidden", window = "address:{m.group(1)}", follow = false }})')
        return ""
    return run("i3-msg", cmd)


def tree():
    return json.loads(run("i3-msg", "-t", "get_tree"))


def focused_ws():
    if HYPR:
        try:
            return json.loads(run("hyprctl", "activeworkspace", "-j"))["name"]
        except Exception:
            return "1"
    return next((w["name"] for w in json.loads(run("i3-msg", "-t", "get_workspaces")) if w["focused"]), "1")


def notify(text):
    subprocess.Popen(["notify-send", "-a", "terminals", "Terminals", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ reading the current terminals
def terminal_windows(node=None, ws=None, out=None):
    if HYPR:
        found = []
        for c in json.loads(run("hyprctl", "clients", "-j") or "[]"):
            if c.get("class") == "Alacritty":
                w = c["workspace"]["name"]
                found.append({"window": c["address"], "id": c["address"], "pid": c["pid"],
                              "ws": "__i3_scratch" if w.startswith("special:") else w, "title": c.get("title", "")})
        return found
    out = [] if out is None else out
    node = tree() if node is None else node
    if node.get("type") == "workspace":
        ws = node.get("name")
    props = node.get("window_properties") or {}
    if node.get("window") and props.get("class") == "Alacritty":
        out.append({"window": node["window"], "id": node["id"], "ws": ws, "title": node.get("name", "")})
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        terminal_windows(child, ws, out)
    return out


def children(pid):
    return [int(x) for x in run("pgrep", "-P", str(pid)).split()]


def descendants(pid):
    found = []
    for c in children(pid):
        found.append(c)
        found += descendants(c)
    return found


def comm(pid):
    try:
        return open(f"/proc/{pid}/comm").read().strip()
    except OSError:
        return ""


def cwd_of(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


def sessions_for(cwd):
    """Claude conversation files for this folder, newest first."""
    folder = os.path.join(PROJECTS, cwd.replace("/", "-").replace(".", "-"))
    files = sorted(glob.glob(folder + "/*.jsonl"), key=os.path.getmtime, reverse=True)
    return [os.path.basename(f)[:-6] for f in files]


def exact_session(pid):
    """The conversation id Claude itself recorded for this process (~/.claude/sessions/<pid>.json), or None."""
    try:
        sid = json.load(open(f"{HOME}/.claude/sessions/{pid}.json")).get("sessionId")
        return sid if sid and os.path.exists(glob.glob(f"{PROJECTS}/*/{sid}.jsonl")[0]) else None
    except Exception:
        return None


def snapshot():
    terms, claims = [], collections.Counter()
    for t in terminal_windows():
        pid = str(t["pid"]) if "pid" in t else run("xdotool", "getwindowpid", str(t["window"])).strip()
        if not pid.isdigit():
            continue
        kids = descendants(int(pid))
        if not kids:
            continue
        claude = next((p for p in kids if comm(p) == "claude"), None)
        cwd = (cwd_of(claude) if claude else None) or cwd_of(kids[0]) or HOME
        entry = {"ws": t["ws"], "scratch": t["ws"] == "__i3_scratch", "cwd": cwd, "title": t["title"][:60]}
        if claude:
            entry["claude"] = True
            entry["session"] = exact_session(claude)
            if not entry["session"]:                                                       # fallback: n-th most recent in this folder
                files = sessions_for(cwd)
                entry["session"] = files[claims[cwd]] if claims[cwd] < len(files) else None
                claims[cwd] += 1
        terms.append(entry)
    terms.sort(key=lambda e: (e["scratch"], e["ws"], e["cwd"]))
    return terms


def read_state():
    try:
        return json.load(open(STATE)).get("terminals", [])
    except Exception:
        return None


def write_state(terms):
    tmp = STATE + ".tmp"
    json.dump({"saved": time.strftime("%Y-%m-%d %H:%M:%S"), "terminals": terms}, open(tmp, "w"), indent=1)
    if os.path.exists(STATE) and terms:
        try:
            os.replace(STATE, STATE + ".prev")        # keep the previous save too
        except OSError:
            pass
    os.replace(tmp, STATE)


def key(terms):
    return json.dumps(terms, sort_keys=True)


# ------------------------------------------------------------------ restoring
def launch(entry):
    cwd = entry["cwd"] if os.path.isdir(entry["cwd"]) else HOME
    cmd = ["alacritty", "--working-directory", cwd]
    if entry.get("claude"):
        resume = f"claude --resume {entry['session']}" if entry.get("session") else "claude --continue"
        cmd += ["-e", "zsh", "-ic", f"{resume}; exec zsh"]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def restore(path=STATE):
    try:
        terms = json.load(open(path)).get("terminals", [])
    except Exception:
        notify("nothing saved to restore")
        return 0
    home_ws = focused_ws()
    opened = 0
    for entry in terms:
        target = STAGE_WS if entry.get("scratch") else (entry["ws"] if entry["ws"] != "1" else "2")
        if focused_ws() != target:
            i3(f"workspace number {target}")
            time.sleep(0.25)
        before = {t["window"] for t in terminal_windows()}
        launch(entry)
        new = None
        for _ in range(40):                              # wait up to 4 s for the window to show up
            time.sleep(0.1)
            fresh = [t for t in terminal_windows() if t["window"] not in before]
            if fresh:
                new = fresh[0]
                break
        if new and entry.get("scratch"):
            i3(f"[id={new['window']}] move scratchpad")
        elif new and new["ws"] != target:                # make sure it lands on its own workspace
            i3(f"[id={new['window']}] move container to workspace number {target}")
        opened += 1
        time.sleep(0.3)
    if focused_ws() != home_ws:
        i3(f"workspace number {home_ws}")
    notify(f"restored {opened} terminal(s)")
    return opened


# ------------------------------------------------------------------ main
def daemon():
    saved = read_state()
    pending, pending_n = None, 0
    while True:
        try:
            now = snapshot()
            if saved is None or len(now) >= len(saved) or pending == key(now):
                if saved is None or key(now) != key(saved):
                    write_state(now)
                    saved = now
                pending, pending_n = None, 0
            else:
                # fewer terminals than before: could be a shutdown in progress, so only believe it once it repeats
                pending = key(now)
        except Exception:
            pass
        time.sleep(10)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if mode == "save":
        write_state(snapshot())
        notify("terminals saved")
    elif mode == "restore":
        restore(sys.argv[2] if len(sys.argv) > 2 else STATE)
    elif mode == "status":
        try:
            data = json.load(open(STATE))
        except Exception:
            print("nothing saved yet"); return
        print("saved", data.get("saved"))
        for e in data["terminals"]:
            print(" ", "scratchpad" if e["scratch"] else "ws " + e["ws"], "|", e["cwd"], "|", ("claude " + str(e.get("session"))) if e.get("claude") else "shell")
    elif mode == "daemon":
        lock = open("/tmp/term-session.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return
        daemon()
    elif mode == "auto":
        lock = open("/tmp/term-session.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return                                       # already running
        if os.path.exists(STATE) and not os.path.exists(FLAG):
            restore()
        daemon()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
