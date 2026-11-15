#!/usr/bin/env bash
# Dashboard weather pane. wttr.in is queried at most every 15 minutes (location by IP, °F/mph);
# the pane redraws from the cached copy every minute, and immediately whenever its width changes.
CACHE=/tmp/dash-weather.json
HERE=$(dirname "$(readlink -f "$0")")

cols() { local c; c=$(stty size </dev/tty 2>/dev/null | awk '{print $2}'); echo "${c:-30}"; }

stale() {
  [ ! -s "$CACHE" ] && return 0
  [ $(( $(date +%s) - $(stat -c %Y "$CACHE") )) -gt 900 ]
}

fetch() {
  curl -s -m 15 -A 'curl' 'https://wttr.in/?format=j1' -o "$CACHE.tmp" &&
    python3 -I -c 'import json,sys; json.load(open(sys.argv[1]))' "$CACHE.tmp" 2>/dev/null &&
    mv "$CACHE.tmp" "$CACHE"
  rm -f "$CACHE.tmp"
}

draw() {
  local out
  out=$(python3 -I "$HERE/weather-render.py" "$CACHE" "$1")
  printf '\033[H\033[J\033[?25l%s' "$out"
}

lastc=""; tick=60
while :; do
  c=$(cols)
  if [ "$c" != "$lastc" ] || [ "$tick" -ge 60 ]; then
    if stale; then
      draw "$c"        # show whatever we have right away (or "no data yet")...
      fetch            # ...then refresh in the background of the user's attention
      c=$(cols)
    fi
    draw "$c"
    lastc=$c; tick=0
  fi
  sleep 1; tick=$((tick + 1))
done
