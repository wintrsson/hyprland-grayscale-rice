#!/usr/bin/env bash
# Super+Shift+D: stats dashboard on its own workspace (1), placed by a fixed layout file
# (~/.config/i3/dashboard-layout.json) so the windows always land in the right spots.
#   left column:   album art over fastfetch
#   middle column: cava visualizer over btop
#   right column:  services (docker + tailscale) over weather
# Press it again to close the dashboard and return to your previous workspace.
WS=1
LAYOUT=~/.config/i3/dashboard-layout.json
hypr=${HYPRLAND_INSTANCE_SIGNATURE:+1}
fs=8; [ -n "$hypr" ] && fs=11.8      # Wayland has no Xft DPI scaling, so the same look needs a bigger font size
current() { [ -n "$hypr" ] && { hyprctl activeworkspace -j | python3 -I -c 'import sys,json; print(json.load(sys.stdin)["name"])'; return; }; i3-msg -t get_workspaces | python3 -I -c 'import sys,json; print([w["name"] for w in json.load(sys.stdin) if w["focused"]][0])'; }

if [ -n "$hypr" ]; then dash_open() { hyprctl clients -j | grep -q '"class": "dash-'; }; else dash_open() { i3-msg -t get_tree | grep -q '"class":"dash-'; }; fi
if dash_open; then
  if [ -n "$hypr" ]; then
    pkill -f 'alacritty --class [d]ash-'; pkill -f 'feh .*class [d]ash-art'
    [ "$(current)" = "$WS" ] && hyprctl dispatch 'hl.dsp.focus({ workspace = "previous" })' >/dev/null
  else
    i3-msg '[class="^dash-"] kill' >/dev/null
    [ "$(current)" = "$WS" ] && i3-msg 'workspace back_and_forth' >/dev/null
  fi
  exit
fi

# go to the dashboard workspace (don't re-issue the switch if we're already on it: auto_back_and_forth would bounce us away)
if [ -n "$hypr" ]; then
  [ "$(current)" = "$WS" ] || hyprctl dispatch "hl.dsp.focus({ workspace = $WS })" >/dev/null
  # Hyprland: window rules in hyprland.lua put each dash-* window in its slot (fixed positions, same look as the i3 layout)
else
  [ "$(current)" = "$WS" ] || i3-msg "workspace number $WS" >/dev/null
  # lay out empty placeholders, then start the programs; each one is swallowed into its own slot
  i3-msg "append_layout $LAYOUT" >/dev/null
fi

~/.config/i3/scripts/art-image.sh &
alacritty --class dash-fetch -o font.size=$fs -e sh -c 'while :; do printf "\033[H\033[J\033[?25l"; out=$(fastfetch -c ~/.config/fastfetch/dashboard.jsonc --pipe false); printf "%s" "$out"; sleep 20; done' &
alacritty --class dash-cava -e python3 -I ~/.config/i3/scripts/viz.py tui &
alacritty --class dash-btop -o font.size=$fs -e btop &
alacritty --class dash-svc -o font.size=$fs -e ~/.config/i3/scripts/svc-pane.sh &
alacritty --class dash-weather -o font.size=$fs -e ~/.config/i3/scripts/weather-pane.sh &
