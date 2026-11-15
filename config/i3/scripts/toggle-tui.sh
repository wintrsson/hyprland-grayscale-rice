#!/usr/bin/env bash
# usage: toggle-tui.sh <window-class> <command...>   (opens a floating terminal app, or closes it if already open)
cls=$1; shift
if pgrep -f "class $cls" >/dev/null; then pkill -f "class $cls"; else alacritty --class "$cls" -e "$@"; fi
