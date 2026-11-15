#!/usr/bin/env bash
# Super+Shift+I: toggle showing the local IP in the dashboard info pane. It is hidden by default, and hidden again after a reboot
# (flag file lives in /tmp).
FLAG=/tmp/show-ip
if [ -e "$FLAG" ]; then rm -f "$FLAG"; msg="IP hidden"; else touch "$FLAG"; msg="IP shown"; fi
for a in $(pgrep -f 'class dash-fetc[h]'); do for sh in $(pgrep -P "$a"); do pkill -P "$sh" -x sleep; done; done   # info pane re-runs fastfetch
notify-send -t 2000 -a ip "$msg"
