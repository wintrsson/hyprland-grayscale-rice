#!/usr/bin/env python3
"""Builds ~/.config/i3/cheatsheet.txt (two columns, ANSI-styled) shown by Super+F1. Edit the SECTIONS below, then run this."""
import os, re

B, D, R, W = "\033[1m", "\033[2m", "\033[0m", "\033[97m"
K = 24      # key column width
COL = 70    # width of one column

LEFT = [
 ("Apps", [
  ("Super+Enter", "terminal"), ("Super+D", "app launcher"), ("Super+P", "switch between open windows"),
  ("Super+`", "drop-down terminal"), ("Super+M", "Spotify player"), ("Super+B", "Bluetooth manager"), ("Super+N", "Wi-Fi manager"), ("Super+A", "Audio: volume and devices"), ("Super+Shift+W", "next wallpaper"), ("Super+Ctrl+W", "wallpaper chooser"),
  ("Super+C", "small floating visualizer"), ("Super+Shift+A", "connect / disconnect AirPods"), ("Super+F1", "this page")]),
 ("Windows", [
  ("Super+Shift+Q", "close window"), ("Super+F", "fullscreen"), ("Super+Shift+Space", "float / tile"),
  ("Super+Space", "cycle focus"), ("Super+J K L ;", "focus left/down/up/right (arrows too)"),
  ("Super+Shift+J K L ;", "move window (arrows too)"), ("Super+Ctrl+J K L ;", "resize window (arrows too)"),
  ("Super+left-drag", "move with the mouse"), ("Super+right-drag", "resize with the mouse"),
  ("Super+H / V", "next window goes right / below"), ("Super+E", "flip the split direction"),
  ("Super+S or W", "group windows as tabs"), ("Super+Z / X", "hide window / bring it back")]),
 ("Dashboard (workspace 1)", [
  ("Super+Shift+D", "open / close the dashboard"), ("Super+Shift+B", "replay the boot intro"),
  ("Super+Shift+S / T", "save / reopen saved terminals"), ("Super+Shift+I", "show / hide the IP address")]),
]
RIGHT = [
 ("Workspaces", [
  ("Super+1 .. 0", "go to workspace"), ("Super+Shift+1 .. 0", "send window to workspace"), ("Super+Tab", "previous workspace"),
  ("automatic", "a new window on workspace 1 gets its own"), ("automatic", "closing the last window returns to 1")]),
 ("Music", [
  ("Media keys", "play-pause / next / previous"), ("Super+Shift+P", "play / pause"), ("Super+]  /  [", "next / previous track"),
  ("Super+Shift+]  /  [", "hold to fast-forward / rewind"), ("Shift+Next/Prev keys", "same: hold to seek"),
  ("Top bar: track title", "click play-pause, right-click next")]),
 ("Screenshots", [
  ("Print", "save to ~/Pictures/Screenshots"), ("Shift+Print", "select a region, copy it")]),
 ("Top bar", [("Pawn", "open / focus chess.com (new workspace)"), ("Bluetooth", "click: Bluetooth manager")]),
 ("System", [
  ("Super+Shift+X", "power menu: L lock  E exit  S sleep  R reboot  P off"), ("Super+Shift+C", "reload the Hyprland config"),
  ("Volume / brightness", "keys as labelled")]),
 ("Where things live", [
  ("~/.config/hypr/", "hyprland.lua (keys, look, rules), hyprlock"), ("~/.config/waybar/", "top bar"),
  ("~/.config/i3/scripts/", "dashboard, intro, screenshots, ..."), ("~/.config/alacritty/", "terminal font + padding"),
  ("~/.config/dunst/", "notifications"), ("~/.config/i3/config", "old i3 session (pick it at login)")]),
]

def vis(s): return len(re.sub(r"\033\[[0-9;]*m", "", s))
def pad(s, n): return s + " " * max(0, n - vis(s))

def column(sections):
    lines = []
    for title, rows in sections:
        lines.append(f"{B}{W}{title}{R} {D}{'─' * (COL - len(title) - 3)}{R}")
        for k, d in rows:
            lines.append(f"{B}{k:<{K}}{R}{d}"[: 400])
        lines.append("")
    return lines

L, Rr = column(LEFT), column(RIGHT)
n = max(len(L), len(Rr))
L += [""] * (n - len(L)); Rr += [""] * (n - len(Rr))
out = [f"  {B}{W}KEYBINDS & TIPS{R}   {D}(q or Esc to close){R}", ""]
out += [f"  {pad(a, COL)}   {b}" for a, b in zip(L, Rr)]
open(os.path.expanduser("~/.config/i3/cheatsheet.txt"), "w").write("\n".join(out) + "\n")
