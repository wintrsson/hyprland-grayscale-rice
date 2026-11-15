#!/usr/bin/env bash
# Waybar chess-pawn module. Prints the pawn; writing "hop" to /tmp/pawn-ctl plays the jump animation (see chess.sh).
P=$'\U000f0859'
ctl=/tmp/pawn-ctl; [ -p "$ctl" ] || mkfifo "$ctl"
show() { printf '<span foreground="%s" rise="%s" size="15pt">%s</span>\n' "$1" "$2" "$P"; }
show '#9a9a9a' 0
while :; do
  read -r cmd < "$ctl"
  [ "$cmd" = hop ] || continue
  for f in "#c8c8c8 4000" "#ffffff 9000" "#c8c8c8 4000" "#9a9a9a 0"; do
    set -- $f; show "$1" "$2"; sleep 0.06
  done
done
