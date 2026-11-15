#!/usr/bin/env bash
# Live "now playing" for polybar (tail = true). Any MPRIS player: Spotify, browsers, mpv...
play=$'\U000f040a'; pause=$'\U000f03e4'; note=$'\U000f0386'
max=44
show() {
  local st=$1 artist=$2 title=$3 icon
  [ -z "$title" ] && { echo ""; return; }
  case $st in Playing) icon=$play;; Paused) icon=$pause;; *) echo ""; return;; esac
  local text="$artist - $title"; [ -z "$artist" ] && text="$title"
  [ ${#text} -gt $max ] && text="${text:0:$((max-1))}…"
  echo "$icon  $text"
}
while true; do
  playerctl --follow metadata --format '{{status}}|{{artist}}|{{title}}' 2>/dev/null |
  while IFS='|' read -r st artist title; do show "$st" "$artist" "$title"; done
  echo ""; sleep 2
done
