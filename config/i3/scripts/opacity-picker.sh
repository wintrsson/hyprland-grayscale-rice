#!/usr/bin/env bash
# Super+O: open the window-opacity popup (press again to close it)
if pgrep -f 'python3 .*[o]pacity-picker.py' >/dev/null; then pkill -f 'python3 .*[o]pacity-picker.py'; exit 0; fi
exec python3 ~/.config/i3/scripts/opacity-picker.py
