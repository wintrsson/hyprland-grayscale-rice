#!/usr/bin/env bash
# Hyprland's log lives in /run (gone after a reboot). Keep the last 600 lines in ~/.cache/hyprland-last.log so a crash
# right after resume can be diagnosed after the next boot. Also snapshots the previous one to hyprland-prev.log.
log=/run/user/$UID/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log
out=$HOME/.cache/hyprland-last.log
[ -e "$out" ] && cp "$out" "$HOME/.cache/hyprland-prev.log"
while [ -e "$log" ]; do
  tail -n 600 "$log" > "$out.tmp" 2>/dev/null && mv "$out.tmp" "$out"
  sleep 2
done
