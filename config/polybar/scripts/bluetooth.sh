#!/usr/bin/env bash
if ! bluetoothctl show 2>/dev/null | grep -q "Powered: yes"; then echo $'\U000f00b2'; exit; fi
dev=$(bluetoothctl devices Connected 2>/dev/null | head -1 | cut -d' ' -f3-)
if [ -n "$dev" ]; then echo $'\U000f00b1'" ${dev:0:22}"; else echo $'\U000f00af'; fi
