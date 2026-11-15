#!/usr/bin/env bash
# Toggle AirPods Pro: connect if away, disconnect if connected.
MAC=74:77:86:0D:F8:6C
bluetoothctl power on >/dev/null
if bluetoothctl info $MAC | grep -q 'Connected: yes'; then
  bluetoothctl disconnect $MAC >/dev/null; msg="AirPods disconnected"
elif timeout 15 bluetoothctl connect $MAC | grep -q 'successful'; then
  msg="AirPods connected"
else msg="AirPods: connect failed (open the case / check they're nearby)"; fi
command -v notify-send >/dev/null && notify-send -t 2000 "$msg"
