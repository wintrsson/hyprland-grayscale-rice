#!/usr/bin/env bash
# Grayscale album art that FILLS its terminal pane, with track info underneath.
# Redraws when the track changes or the pane is resized.
last=""
trap 'last=""' WINCH
raw=/tmp/dash-art-raw.img
crop=/tmp/dash-art-crop.png
while true; do
  url=$(playerctl metadata mpris:artUrl 2>/dev/null)
  title=$(playerctl metadata title 2>/dev/null)
  artist=$(playerctl metadata artist 2>/dev/null)
  album=$(playerctl metadata album 2>/dev/null)
  cols=$(tput cols); rows=$(tput lines)
  key="$url|$title|$artist|${cols}x${rows}"
  if [ "$key" != "$last" ]; then
    last=$key
    clear
    if [ -z "$title" ]; then
      printf '\n  nothing playing\n'
    else
      img=""
      case $url in
        http*)    curl -s -m 6 -o "$raw" "$url" && img=$raw ;;
        file://*) img=${url#file://} ;;
      esac
      art_rows=$(( rows - 5 ))
      [ "$art_rows" -lt 4 ] && art_rows=4
      if [ -n "$img" ]; then
        # Never crop the top/bottom: if the pane is wider than the cover, show the whole cover with thin side margins;
        # if it's narrower, crop only the sides. (A cell is ~0.43 as wide as it is tall.)
        read -r W H < <(magick identify -format '%w %h' "$img" 2>/dev/null)
        if [ -n "$W" ] && [ -n "$H" ]; then
          read -r geom size < <(awk -v W="$W" -v H="$H" -v c="$cols" -v r="$art_rows" 'BEGIN{
            ar = (c*0.43)/r; img = W/H;
            if (ar >= img) { cu = int(r*img/0.43); if (cu > c) cu = c; printf "%dx%d+0+0 %dx%d", W, H, cu, r }
            else { iw = H*ar; printf "%dx%d+%d+0 %dx%d", iw, H, (W-iw)/2, c, r } }')
          magick "$img" -crop "$geom" +repage -colorspace Gray "$crop" 2>/dev/null && {
            # round the corners: clear the corner pixels (radius = 1/7 of the shorter side)
            cw=$(magick identify -format %w "$crop"); ch=$(magick identify -format %h "$crop")
            rr=$(( (cw < ch ? cw : ch) / 7 ))
            magick "$crop" \( +clone -alpha extract -draw "fill black polygon 0,0 0,$rr $rr,0 fill white circle $rr,$rr $rr,0" \
              \( +clone -flip \) -compose Multiply -composite \( +clone -flop \) -compose Multiply -composite \) \
              -alpha off -compose CopyOpacity -composite "$crop" 2>/dev/null
            chafa -f symbols --symbols half --dither none --stretch --align mid -s "$size" "$crop"
          }
        fi
      fi
      printf '\n\033[1m%s\033[0m\n%s\n\033[2m%s\033[0m' "$title" "$artist" "$album"
    fi
  fi
  sleep 1.5
done
