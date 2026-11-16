#!/usr/bin/env bash
# usage: wallpaper.sh next | prev | random | /path/to/image | reload     -- talks to the wallpaper daemon (parallax.py)
mkdir -p ~/.cache/parallax
case "$1" in
  reload) pkill -USR1 -f 'python3 .*[p]arallax.py' ;;
  next|prev|random) echo "$1" > ~/.cache/parallax/cmd; pkill -USR2 -f 'python3 .*[p]arallax.py' ;;
  *) [ -e "$1" ] && { echo "$1" > ~/.cache/parallax/cmd; pkill -USR2 -f 'python3 .*[p]arallax.py'; } ;;
esac
