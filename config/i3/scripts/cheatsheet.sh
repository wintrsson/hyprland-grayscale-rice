#!/usr/bin/env bash
# Super+F1: show / hide the keybinds page (a floating terminal running `less`).
if pgrep -f 'alacritty --class cheatshee[t]' >/dev/null; then pkill -f 'alacritty --class cheatshee[t]'; exit 0; fi
fs=8.6; [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] && fs=12.5      # same look on X11 (scaled by DPI) and Wayland
exec alacritty --class cheatsheet -o font.size=$fs -e ~/.config/i3/scripts/cheatsheet-view.sh
