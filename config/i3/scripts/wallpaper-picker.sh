#!/usr/bin/env bash
# Super+Ctrl+W: open the wallpaper chooser (press again to close it)
if pgrep -f 'python3 .*[w]allpaper-picker.py' >/dev/null; then pkill -f 'python3 .*[w]allpaper-picker.py'; exit 0; fi
exec python3 ~/.config/i3/scripts/wallpaper-picker.py
