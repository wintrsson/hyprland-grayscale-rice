#!/usr/bin/env bash
# Pop a small grayscale notification with the album art whenever the track changes.
# Skipped while the dashboard is on screen (it already shows the track, and the pop-up would cover its panes).
art=/tmp/nowplaying-art.jpg; gray=/tmp/nowplaying-art-gray.png; last=""

dashboard_visible() {
  if [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ]; then
    [ "$(hyprctl activeworkspace -j 2>/dev/null | python3 -I -c 'import sys,json; print(json.load(sys.stdin)["name"])' 2>/dev/null)" = 1 ] &&
      hyprctl clients -j 2>/dev/null | grep -q '"class": "dash-'
  else
    [ "$(i3-msg -t get_workspaces 2>/dev/null | python3 -I -c 'import sys,json; print([w["name"] for w in json.load(sys.stdin) if w["focused"]][0])' 2>/dev/null)" = 1 ] &&
      i3-msg -t get_tree 2>/dev/null | grep -q '"class":"dash-'
  fi
}

while true; do
  playerctl --follow metadata --format '{{mpris:artUrl}}|{{artist}}|{{title}}|{{album}}' 2>/dev/null |
  while IFS='|' read -r url artist title album; do
    [ -z "$title" ] || [ "$title" = "$last" ] && continue
    last=$title
    dashboard_visible && continue
    icon=audio-x-generic; src=""
    case $url in
      file://*) src=${url#file://} ;;
      http*)    curl -s -m 5 -o "$art" "$url" && src=$art ;;
    esac
    [ -n "$src" ] && magick "$src" -resize 96x96^ -gravity center -extent 96x96 -colorspace Gray -colorspace sRGB "$gray" 2>/dev/null && icon=$gray
    notify-send -a nowplaying -t 3500 -i "$icon" -h string:x-dunst-stack-tag:nowplaying "$title" "$artist${album:+  ·  $album}"
  done
  sleep 2
done
