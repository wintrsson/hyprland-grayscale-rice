#!/usr/bin/env bash
# Super+C: show/hide a small floating audio visualizer.
if pgrep -f 'class cavaterm' >/dev/null; then pkill -f 'class cavaterm'; else alacritty --class cavaterm -e python3 -I ~/.config/i3/scripts/viz.py tui; fi
