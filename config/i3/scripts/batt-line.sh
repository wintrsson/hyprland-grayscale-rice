#!/usr/bin/env bash
# One compact battery line for the dashboard info pane: "75%  discharging  2h16m"  /  "88%  charging  0h42m"  /  "100%  full"
b=/sys/class/power_supply/BAT0
cap=$(<"$b/capacity"); st=$(<"$b/status")
if [ -r "$b/energy_now" ]; then now=$(<"$b/energy_now"); full=$(<"$b/energy_full"); p=$(<"$b/power_now")
else now=$(<"$b/charge_now"); full=$(<"$b/charge_full"); p=$(<"$b/current_now"); fi
mins=""
case $st in
  Discharging) [ "${p:-0}" -gt 0 ] && mins=$(( now * 60 / p )) ;;
  Charging)    [ "${p:-0}" -gt 0 ] && mins=$(( (full - now) * 60 / p )) ;;
esac
t=""; [ -n "$mins" ] && t=$(printf '  %dh%02dm' $((mins / 60)) $((mins % 60)))
# Plugged in but the battery is parked at its charge limit (e.g. Dell "charge until 90%"): the kernel calls that
# "Not charging", which reads like a fault. Say what is really going on.
ac=""; for a in /sys/class/power_supply/AC /sys/class/power_supply/ADP1 /sys/class/power_supply/ACAD; do [ -r "$a/online" ] && ac=$(<"$a/online") && break; done
if [ "$st" = "Not charging" ] && [ "$ac" = "1" ]; then
  lim=""; [ -r "$b/charge_control_end_threshold" ] && lim="  (limit $(<"$b/charge_control_end_threshold")%)"
  echo "${cap}%  plugged in${lim}"
else
  echo "${cap}%  ${st,,}${t}"
fi
