#!/usr/bin/env python3
"""Grayscale Wi-Fi manager (Super+N or click the bar icon): a small TUI over nmcli that matches the rest of the rice.
Keys:  up/down or j/k  move   Enter  connect   r  rescan   d  disconnect   x  forget   h  hidden network   w  radio on/off   q / Esc  close
"""
import curses, subprocess, threading, time, re

SIG = "󰤟󰤢󰤥󰤨"      # same icons as the top bar
LOCK = "󰌾"
state = {"nets": [], "known": set(), "dev": None, "conn": None, "ip": "", "radio": True, "msg": "", "busy": False}
mu = threading.Lock()


def nm(*args, timeout=25, inp=None):
    try:
        r = subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout, input=inp)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def split(line):
    """split an nmcli -t line on unescaped colons"""
    return [p.replace("\\:", ":").replace("\\\\", "\\") for p in re.split(r"(?<!\\):", line)]


def refresh():
    rc, out = nm("-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "no")
    nets = {}
    if rc == 0:
        for ln in out.splitlines():
            f = split(ln)
            if len(f) < 4 or not f[1]:
                continue
            inuse, ssid, sig, sec = f[0] == "*", f[1], int(f[2] or 0), f[3]
            cur = nets.get(ssid)
            if cur is None or inuse or (not cur["inuse"] and sig > cur["sig"]):
                nets[ssid] = {"ssid": ssid, "sig": sig, "sec": sec not in ("", "--"), "inuse": inuse}
    rc, out = nm("-t", "-f", "NAME,TYPE", "connection", "show")
    known = {split(l)[0] for l in out.splitlines() if len(split(l)) > 1 and "wireless" in split(l)[1]}
    rc, out = nm("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev")
    dev = conn = None
    for ln in out.splitlines():
        f = split(ln)
        if len(f) >= 4 and f[1] == "wifi":
            dev = f[0]
            conn = f[3] if f[2] == "connected" else None
    ip = ""
    if dev and conn:
        rc, out = nm("-t", "-g", "IP4.ADDRESS", "dev", "show", dev)
        ip = out.strip().split("\n")[0].split("/")[0]
    rc, out = nm("radio", "wifi")
    order = sorted(nets.values(), key=lambda n: (not n["inuse"], -n["sig"], n["ssid"].lower()))
    with mu:
        state.update(nets=order, known=known, dev=dev, conn=conn, ip=ip, radio=out.strip() == "enabled")


def poller():
    last_scan = 0
    while True:
        if time.time() - last_scan > 25:
            nm("dev", "wifi", "rescan", timeout=10)
            last_scan = time.time()
        refresh()
        time.sleep(3)


def run_bg(label, *args, inp=None, done=None):
    def work():
        with mu:
            state["busy"] = True
            state["msg"] = label
        rc, out = nm(*args, timeout=40, inp=inp)
        refresh()
        with mu:
            state["busy"] = False
            if rc == 0:
                state["msg"] = done or "done"
            else:
                state["msg"] = (out.strip().splitlines() or ["failed"])[-1][:90]
    threading.Thread(target=work, daemon=True).start()


def bars(sig):
    return SIG[min(3, max(0, (sig - 1) // 25))]


def prompt(scr, title, secret=True):
    """one-line input at the bottom; Enter = ok, Esc = cancel, Tab = show/hide"""
    buf, show = "", False
    h, w = scr.getmaxyx()
    curses.curs_set(1)
    scr.timeout(-1)
    while True:
        scr.move(h - 2, 0); scr.clrtoeol()
        shown = buf if (show or not secret) else "•" * len(buf)
        scr.addstr(h - 2, 2, (title + " ")[: w - 4], curses.color_pair(3))
        x = 2 + len(title) + 1
        scr.addstr(h - 2, x, shown[-(w - x - 2):], curses.color_pair(1) | curses.A_BOLD)
        scr.refresh()
        k = scr.get_wch()
        if k in ("\n", "\r") or k == curses.KEY_ENTER:
            res = buf
            break
        if k == "\x1b":
            res = None
            break
        if k == "\t":
            show = not show
        elif k in ("\x7f", "\b") or k == curses.KEY_BACKSPACE:
            buf = buf[:-1]
        elif isinstance(k, str) and k.isprintable():
            buf += k
    curses.curs_set(0)
    scr.timeout(250)
    return res


def draw(scr, sel):
    scr.erase()
    h, w = scr.getmaxyx()
    with mu:
        s = dict(state); nets = list(s["nets"])
    c1, c2, c3, c4 = (curses.color_pair(i) for i in (1, 2, 3, 4))
    pad = 3
    inner = max(20, w - 2 * pad)
    # header
    scr.addstr(1, pad, "wifi", c1 | curses.A_BOLD)
    radio = "on" if s["radio"] else "off"
    scr.addstr(1, w - pad - len("radio " + radio), "radio " + radio, c3)
    if s["conn"]:
        info = f"{s['conn']}   {s['ip']}" if s["ip"] else s["conn"]
        scr.addstr(2, pad, ("● " + info)[:inner], c2)
    else:
        scr.addstr(2, pad, "○ not connected", c3)
    scr.addstr(3, pad, "─" * inner, c4)
    # list
    top, bottom = 5, h - 6
    rows = max(1, bottom - top)
    if not s["radio"]:
        scr.addstr(top, pad, "wifi radio is off  (press w to turn it on)", c3)
    elif not nets:
        scr.addstr(top, pad, "scanning…" if not s["nets"] else "no networks found", c3)
    start = max(0, min(sel - rows // 2, len(nets) - rows))
    for i, n in enumerate(nets[start:start + rows]):
        y = top + i
        idx = start + i
        dot = "●" if n["inuse"] else "○"
        tag = "connected" if n["inuse"] else ("saved" if n["ssid"] in s["known"] else "")
        lock = LOCK if n["sec"] else " "
        name_w = inner - 22
        line = f" {dot}  {n['ssid'][:name_w]:<{name_w}}  {bars(n['sig'])}  {lock}  {tag:<9}"
        attr = (c1 | curses.A_BOLD) if n["inuse"] else c1
        if idx == sel:
            scr.addstr(y, pad - 1, (" " + line).ljust(inner + 2)[:inner + 2], curses.color_pair(5))
        else:
            scr.addstr(y, pad, line[:inner], attr if n["inuse"] else c1 if n["ssid"] in s["known"] else c3)
    # footer
    scr.addstr(h - 5, pad, "─" * inner, c4)
    msg = s["msg"] + ("  …" if s["busy"] else "")
    scr.addstr(h - 4, pad, msg[:inner], c2 if not s["busy"] else c3)
    scr.addstr(h - 2, pad, "↵ connect    r rescan    d disconnect"[:inner], c4)
    scr.addstr(h - 1, pad, "x forget     h hidden    w radio    q close"[:inner], c4)
    scr.refresh()
    return nets


def main(scr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    # 1 text  2 bright  3 dim  4 borders  5 selected row  (256-color grays, like the rest of the rice)
    curses.init_pair(1, 252, -1)
    curses.init_pair(2, 255, -1)
    curses.init_pair(3, 244, -1)
    curses.init_pair(4, 239, -1)
    curses.init_pair(5, 255, 237)
    scr.timeout(250)
    threading.Thread(target=poller, daemon=True).start()
    sel = 0
    while True:
        nets = draw(scr, sel)
        sel = max(0, min(sel, len(nets) - 1))
        try:
            k = scr.get_wch()
        except curses.error:
            continue
        if k in ("q", "\x1b"):
            return
        n = nets[sel] if nets else None
        if k in (curses.KEY_DOWN, "j"):
            sel = min(sel + 1, max(0, len(nets) - 1))
        elif k in (curses.KEY_UP, "k"):
            sel = max(sel - 1, 0)
        elif k == "r":
            run_bg("scanning", "dev", "wifi", "rescan", done="scan started")
        elif k == "w":
            run_bg("switching radio", "radio", "wifi", "off" if state["radio"] else "on", done="ok")
        elif k == "d" and state["dev"]:
            run_bg("disconnecting", "dev", "disconnect", state["dev"], done="disconnected")
        elif k == "x" and n and n["ssid"] in state["known"]:
            run_bg(f"forgetting {n['ssid']}", "connection", "delete", "id", n["ssid"], done="forgot " + n["ssid"])
        elif k == "h":
            ssid = prompt(scr, "hidden network name:", secret=False)
            if ssid:
                pw = prompt(scr, "password (empty = open):")
                if pw is not None:
                    args = ["dev", "wifi", "connect", ssid, "hidden", "yes"] + (["password", pw] if pw else [])
                    run_bg(f"connecting to {ssid}", *args, done="connected to " + ssid)
        elif k in ("\n", "\r", curses.KEY_ENTER) and n and not n["inuse"]:
            ssid = n["ssid"]
            if ssid in state["known"]:
                run_bg(f"connecting to {ssid}", "--wait", "25", "connection", "up", "id", ssid, done="connected to " + ssid)
            elif not n["sec"]:
                run_bg(f"connecting to {ssid}", "--wait", "25", "dev", "wifi", "connect", ssid, done="connected to " + ssid)
            else:
                pw = prompt(scr, f"password for {ssid}:")
                if pw:
                    run_bg(f"connecting to {ssid}", "--wait", "25", "dev", "wifi", "connect", ssid, "password", pw,
                           done="connected to " + ssid)


if __name__ == "__main__":
    curses.wrapper(main)
