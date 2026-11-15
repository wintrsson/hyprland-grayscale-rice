#!/usr/bin/env bash
# Dashboard album art as a real image window: grayscale cover with smooth rounded corners,
# plus title / artist / album underneath. The image is rendered at the window's exact size
# (and re-rendered when the window is resized or the track changes), so no zooming is involved.
out=/tmp/dash-art-view.png
raw=/tmp/dash-art-raw.img
mask=/tmp/dash-art-mask.png
cover=/tmp/dash-art-cover.png
cache=/tmp/dash-art-base.png   # cover + text, without the progress bar
FONT=$(fc-match 'JetBrainsMono Nerd Font' -f '%{file}')
FONTB=$(fc-match 'JetBrainsMono Nerd Font:bold' -f '%{file}')
BG='#1b1b1b'
# cover corners use the same radius as every window (picom's corner-radius)
WINDOW_R=$(grep -o 'corner-radius = [0-9]*' ~/.config/picom/picom.conf | grep -o '[0-9]*$')
WINDOW_R=${WINDOW_R:-12}

trunc() { local s=$1 n=$2; [ "$n" -lt 4 ] && n=4; [ ${#s} -gt "$n" ] && s="${s:0:$((n - 1))}…"; printf '%s' "$s"; }

# current size of the art window ("W H"); a sensible default before it exists
winsize() {
  local id g
  id=$(xdotool search --class dash-art 2>/dev/null | head -1)
  [ -n "$id" ] && g=$(xdotool getwindowgeometry "$id" 2>/dev/null | awk '/Geometry/{print $2}')
  g=${g:-$([ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] && echo 572x680 || echo 629x661)}
  echo "${g%x*} ${g#*x}"
}

render() {
  local W H url title artist album img="" m S X Y R t1 t2 t3 need y1 y2 y3
  read -r W H < <(winsize)
  [ "$W" -lt 160 ] && W=160
  [ "$H" -lt 160 ] && H=160

  IFS=$'\x1f' read -r url title artist album < <(playerctl metadata --format $'{{mpris:artUrl}}\x1f{{title}}\x1f{{artist}}\x1f{{album}}' 2>/dev/null)

  if [ -z "$title" ]; then
    rm -f "$cache"
    magick -size ${W}x${H} "xc:$BG" -font "$FONT" -pointsize $((W / 22)) -fill '#8a8a8a' \
      -gravity center -annotate +0+0 'nothing playing' "$out.tmp.png" && mv "$out.tmp.png" "$out"
    return
  fi

  case $url in
    http*)    # covers are cached on disk by URL, so replays work offline; slow links get a longer timeout and retries
              c=$HOME/.cache/dash-art/$(printf '%s' "$url" | md5sum | cut -c1-16); mkdir -p "${c%/*}"
              [ -s "$c" ] || curl -s -m 25 --retry 2 -o "$c.tmp" "$url" && [ -s "$c.tmp" ] && mv "$c.tmp" "$c"
              [ -s "$c" ] && img=$c ;;
    file://*) img=${url#file://} ;;
  esac

  # layout: square cover with margins, text block underneath; everything scales with the window
  m=$((W / 40))                      # one margin, used on the top, left and right
  S=$((W - 2 * m)); X=$m; Y=$m; R=$WINDOW_R
  if [ $((Y + S + m + 140)) -gt "$H" ]; then   # very short pane: shrink the cover so the text still fits
    S=$((H - Y - m - 140)); [ "$S" -lt 80 ] && S=80; X=$(((W - S) / 2))
  fi
  t1=16; t2=16; t3=16                # same size as the other dashboard panes (alacritty font.size=8)
  LH=24                               # line spacing
  y1=$((Y + S + 14)); y2=$((y1 + LH)); y3=$((y2 + LH))
  BX=$X; BS=$S; BY=$(( (y3 + 20 + H) / 2 - 8 ))   # centered between the text and the bottom edge; BW=$W; BH=$H   # where the progress bar goes (used by bar)

  magick -size ${W}x${H} "xc:$BG" "$out.base.png"

  if [ -n "$img" ]; then
    magick -size ${S}x${S} xc:black -fill white -draw "roundrectangle 0,0 $((S - 1)),$((S - 1)) $R,$R" "$mask"
    magick "$img" -colorspace Gray -resize ${S}x${S}^ -gravity center -extent ${S}x${S} \
      "$mask" -alpha off -compose CopyOpacity -composite "$cover" &&
      magick "$out.base.png" "$cover" -geometry +$X+$Y -compose over -composite "$out.base.png"
  fi

  magick "$out.base.png" -gravity NorthWest \
    -font "$FONTB" -pointsize $t1 -fill '#f2f2f2' -annotate +$X+$y1 "$(trunc "$title"  $((S * 10 / (t1 * 6))))" \
    -font "$FONT"  -pointsize $t2 -fill '#cfcfcf' -annotate +$X+$y2 "$(trunc "$artist" $((S * 10 / (t2 * 6))))" \
    -font "$FONT"  -pointsize $t3 -fill '#7a7a7a' -annotate +$X+$y3 "$(trunc "$album"  $((S * 10 / (t3 * 6))))" \
    "$cache.tmp.png" && mv "$cache.tmp.png" "$cache"
  rm -f "$out.base.png"
  bar
}

fmt() { awk -v t="$1" 'BEGIN{t=int(t); printf "%d:%02d", t/60, t%60}'; }

# playback progress under the text: thin rounded track + fill, elapsed / total underneath. Cheap (one composite per call).
bar() {
  [ -f "$cache" ] || return
  local pos len fw ty th=6 fillargs
  len=$(playerctl metadata mpris:length 2>/dev/null)
  pos=$(playerctl position 2>/dev/null)
  if [ -z "$len" ] || [ "${len:-0}" -le 0 ] 2>/dev/null || [ -z "$pos" ]; then cp "$cache" "$out.tmp.png" && mv "$out.tmp.png" "$out"; return; fi
  len=$((len / 1000000))
  fw=$(awk -v p="$pos" -v l="$len" -v s="$BS" 'BEGIN{f=p/l; if(f>1)f=1; if(f<0)f=0; printf "%d", f*s}')
  ty=$BY
  fillargs=(); [ "$fw" -ge 4 ] && fillargs=(-fill '#d8d8d8' -draw "roundrectangle $BX,$ty $((BX + fw)),$((ty + th)) 3,3")
  magick "$cache" -gravity NorthWest \
    -fill '#333333' -draw "roundrectangle $BX,$ty $((BX + BS - 1)),$((ty + th)) 3,3" \
    "${fillargs[@]}" \
    "$out.tmp.png" && mv "$out.tmp.png" "$out"
}

last=""
changed() {
  local key size
  key=$(playerctl metadata --format '{{mpris:artUrl}}|{{title}}|{{artist}}' 2>/dev/null)
  size=$(winsize)
  key="$key|$size"
  [ "$key" = "$last" ] && return 1
  last=$key
  return 0
}

# Open the window at once so it appears together with the other panes: reuse the last picture (or a dark placeholder) now,
# and let the updater loop draw the real cover a moment later (it renders as soon as /tmp/dash-art-dirty exists).
if [ ! -s "$out" ]; then read -r W0 H0 < <(winsize); magick -size ${W0}x${H0} "xc:$BG" "$out"; fi
touch /tmp/dash-art-dirty
# Deliberate glitch: when /tmp/dash-art-glitch exists, flash a few stretched / sliced / shifted copies of the
# current image, then restore it. (Created by glitch.py as the dashboard flickers in.)
glitch() {
  local good="$out.good.png" w h n ox
  cp "$out" "$good" 2>/dev/null || return
  read -r w h < <(identify -format '%w %h' "$good")
  for n in 1 2 3 4 5 6; do
    case $((RANDOM % 5)) in
      0) magick "$good" -resize $((w * (150 + RANDOM % 120) / 100))x${h}! -gravity center -crop ${w}x${h}+0+0 +repage "$out.g.png" ;;
      1) magick "$good" -resize ${w}x$((h * (40 + RANDOM % 50) / 100))! -gravity north -background '#1b1b1b' -extent ${w}x${h} "$out.g.png" ;;
      2) ox=$((RANDOM % 90 + 20)); magick "$good" \( +clone -crop ${w}x$((h / 5))+0+$((RANDOM % (h * 3 / 5))) +repage -roll +${ox}+0 \) \
           -geometry +0+$((RANDOM % (h * 3 / 5))) -composite "$out.g.png" ;;
      3) magick "$good" -resize $((w / (3 + RANDOM % 4)))x$((h / (3 + RANDOM % 4)))! -filter point -resize ${w}x${h}! "$out.g.png" ;;
      4) magick "$good" -channel R -roll +14+0 +channel -channel B -roll -14+0 +channel "$out.g.png" ;;
    esac
    [ -f "$out.g.png" ] && mv "$out.g.png" "$out"
    sleep 0.$((8 + RANDOM % 6))
  done
  mv "$good" "$out"
}

( while :; do
    sleep 0.1
    if [ -e /tmp/dash-art-glitch ]; then rm -f /tmp/dash-art-glitch; glitch; continue; fi
    # a track change (flagged instantly by the follower below) re-renders within 0.1 s; otherwise check every second
    if [ -e /tmp/dash-art-dirty ]; then rm -f /tmp/dash-art-dirty; changed; render; n=0; continue; fi
    # for the first 6 s after start, follow the window size closely (it gets resized right after it opens)
    [ "$n" -lt 60 ] && changed && render
    n=$((n + 1)); [ $((n % 10)) -eq 0 ] && { if changed; then render; else bar; fi; }
  done ) &
updater=$!
# follower: playerctl reports metadata changes the moment the player publishes them
( playerctl --follow metadata --format '{{mpris:artUrl}}|{{title}}|{{artist}}' 2>/dev/null | while IFS= read -r _; do touch /tmp/dash-art-dirty; done ) &
follower=$!
trap 'kill "$updater" "$follower" 2>/dev/null' EXIT

# the window itself (foreground); closing it ends the script and the updater
feh --scale-down -B black --class dash-art -R 0.08 "$out"
