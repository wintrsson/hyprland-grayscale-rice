#!/usr/bin/env bash
# Waybar play/pause button icon: shows "pause" while something plays, "play" otherwise. Updates the moment the player changes state.
play=$'\U000f040a'; pause=$'\U000f03e4'
emit() { case $1 in Playing) echo "$pause" ;; *) echo "$play" ;; esac; }
emit Stopped
while :; do
  playerctl --follow status 2>/dev/null | while IFS= read -r s; do emit "$s"; done
  emit Stopped; sleep 2
done
