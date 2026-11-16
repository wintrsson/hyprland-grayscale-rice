#!/usr/bin/env bash
# Downloads the black-and-white wallpapers listed in wallpapers.tsv from Wikimedia Commons into ~/Pictures/wall.<name>.jpg
# (2560x1440, true grayscale) and writes ~/Pictures/wallpaper-credits.txt. Safe to re-run: existing files are skipped.
# They are photographs that were shot / edited as black and white (not colour photos made grey). CC0 ones need no credit;
# the CC BY / CC BY-SA ones are credited in the credits file.
set -u
here=$(cd "$(dirname "$0")" && pwd)
dest=${WALLPAPER_DIR:-$HOME/Pictures}
mkdir -p "$dest"
ua="dotfiles-wallpaper-fetch/1.0 (personal desktop customization)"
credits="$dest/wallpaper-credits.txt"
: > "$credits"
ok=0; fail=0
while IFS=$'\t' read -r name file lic author; do
  case "$name" in ''|'#'*) continue ;; esac
  out="$dest/wall.$name.jpg"
  { printf '%s\t%s\t%s\t%s\n' "wall.$name.jpg" "$file" "$lic" "$author"; } >> "$credits"
  [ -s "$out" ] && { ok=$((ok + 1)); continue; }
  enc=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1].replace(" ", "_")))' "$file")
  tmp=$(mktemp --suffix=.jpg)
  for attempt in 1 2 3 4; do
    curl -fsSL -m 180 -A "$ua" -o "$tmp" "https://commons.wikimedia.org/wiki/Special:FilePath/$enc?width=2560" && identify "$tmp" >/dev/null 2>&1 && break
    sleep 3
  done
  if identify "$tmp" >/dev/null 2>&1 && magick "$tmp" -colorspace Gray -resize 2560x1440^ -gravity center -extent 2560x1440 -quality 92 "$out" 2>/dev/null; then
    echo "  ok   $name"; ok=$((ok + 1))
  else
    echo "  FAIL $name"; fail=$((fail + 1))
  fi
  rm -f "$tmp"
done < "$here/wallpapers.tsv"
echo "wallpapers: $ok ready, $fail failed (credits: $credits)"
