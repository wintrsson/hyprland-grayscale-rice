#!/usr/bin/env python3
"""Grayscale audio manager (Super+A or click the volume in the bar): pick the output / input device and set its volume.
Keys:  up/down j/k  select device   left/right h/l  volume -/+5   Enter  make default   m  mute   Tab  outputs <-> inputs   q / Esc  close
"""
import curses, json, re, subprocess, time

KINDS = {"out": ("sink", "sinks", "output"), "in": ("source", "sources", "input")}


def pa(*args):
    try:
        r = subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=5)
        return r.stdout
    except Exception:
        return ""


def devices(kind):
    one, many, _ = KINDS[kind]
    try:
        data = json.loads(pa("-f", "json", "list", many) or "[]")
    except ValueError:
        data = []
    default = pa(f"get-default-{one}").strip()
    out = []
    for d in data:
        if d["name"].endswith(".monitor"):
            continue
        vols = list(d.get("volume", {}).values())
        pct = int(vols[0]["value_percent"].rstrip("%")) if vols else 0
        out.append({"name": d["name"], "desc": d.get("description") or d["name"], "vol": pct,
                    "mute": d.get("mute", False), "default": d["name"] == default,
                    "virtual": "easyeffects" in d["name"]})
    out.sort(key=lambda x: (not x["default"], x["desc"].lower()))
    return out


def set_default(kind, name):
    one = KINDS[kind][0]
    pa(f"set-default-{one}", name)
    if kind == "out":   # move playing streams to the new device so the sound follows
        for ln in pa("list", "short", "sink-inputs").splitlines():
            pa("move-sink-input", ln.split("\t")[0], name)


def set_volume(kind, name, pct):
    pa(f"set-{KINDS[kind][0]}-volume", name, f"{max(0, min(100, pct))}%")


def draw(scr, kind, devs, sel, msg):
    scr.erase()
    h, w = scr.getmaxyx()
    c1, c2, c3, c4 = (curses.color_pair(i) for i in (1, 2, 3, 4))
    pad = 3
    inner = max(30, w - 2 * pad)
    scr.addstr(1, pad, "audio", c2 | curses.A_BOLD)
    tabs = [("output", "out"), ("input", "in")]
    x = w - pad - 20
    for label, k in tabs:
        scr.addstr(1, x, label, (c2 | curses.A_BOLD) if k == kind else c3)
        x += len(label) + 4
    scr.addstr(2, pad, "─" * inner, c4)
    top = 4
    rows = max(1, (h - 8) // 2)
    if not devs:
        scr.addstr(top, pad, "no devices", c3)
    start = max(0, min(sel - rows // 2, len(devs) - rows))
    bar_w = 10
    for i, d in enumerate(devs[start:start + rows]):
        y = top + i * 2
        idx = start + i
        dot = "●" if d["default"] else "○"
        name_w = inner - bar_w - 14
        label = d["desc"] + ("  (virtual)" if d["virtual"] else "")
        filled = round(bar_w * min(d["vol"], 100) / 100)
        bar = "━" * filled + "─" * (bar_w - filled)
        vol = "muted" if d["mute"] else f"{d['vol']}%"
        line = f" {dot}  {label[:name_w]:<{name_w}}  {bar}  {vol:>5}"
        if idx == sel:
            scr.addstr(y, pad - 1, (" " + line).ljust(inner + 2)[:inner + 2], curses.color_pair(5))
        else:
            scr.addstr(y, pad, line[:inner], c2 if d["default"] else c1 if not d["mute"] else c3)
    scr.addstr(h - 5, pad, "─" * inner, c4)
    scr.addstr(h - 4, pad, msg[:inner], c2)
    scr.addstr(h - 2, pad, "↵ make default    ←/→ volume    m mute"[:inner], c4)
    scr.addstr(h - 1, pad, "tab output/input    q close"[:inner], c4)
    scr.refresh()


def main(scr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, 252, -1)
    curses.init_pair(2, 255, -1)
    curses.init_pair(3, 244, -1)
    curses.init_pair(4, 239, -1)
    curses.init_pair(5, 255, 237)
    scr.timeout(300)
    kind, sel, msg = "out", 0, ""
    devs = devices(kind)
    sel = next((i for i, d in enumerate(devs) if d["default"]), 0)
    last = time.time()
    while True:
        draw(scr, kind, devs, sel, msg)
        try:
            k = scr.get_wch()
        except curses.error:
            k = None
        if k in ("q", "\x1b"):
            return
        d = devs[sel] if devs else None
        changed = False
        if k in (curses.KEY_DOWN, "j"):
            sel = min(sel + 1, max(0, len(devs) - 1))
        elif k in (curses.KEY_UP, "k"):
            sel = max(sel - 1, 0)
        elif k in ("\t", curses.KEY_BTAB):
            kind = "in" if kind == "out" else "out"
            devs, sel, msg = devices(kind), 0, ""
            sel = next((i for i, x in enumerate(devs) if x["default"]), 0)
        elif d and k in (curses.KEY_RIGHT, "l", "+"):
            set_volume(kind, d["name"], d["vol"] + 5); changed = True
        elif d and k in (curses.KEY_LEFT, "h", "-"):
            set_volume(kind, d["name"], d["vol"] - 5); changed = True
        elif d and k == "m":
            pa(f"set-{KINDS[kind][0]}-mute", d["name"], "toggle"); changed = True
        elif d and k in ("\n", "\r", curses.KEY_ENTER):
            set_default(kind, d["name"]); msg = f"{KINDS[kind][2]}: {d['desc']}"; changed = True
        if changed or time.time() - last > 1:
            name = devs[sel]["name"] if devs else None
            devs = devices(kind)
            sel = next((i for i, x in enumerate(devs) if x["name"] == name), min(sel, max(0, len(devs) - 1)))
            last = time.time()


if __name__ == "__main__":
    curses.wrapper(main)
