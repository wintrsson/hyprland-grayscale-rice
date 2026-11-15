#!/usr/bin/env bash
# Local IP for the dashboard info pane. Hidden by default; Super+Shift+I (show-ip.sh) reveals it until toggled off or reboot.
if [ -e /tmp/show-ip ]; then ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -1; else echo "•••.•••.•••.•••"; fi
