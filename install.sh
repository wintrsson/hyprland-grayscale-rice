#!/usr/bin/env bash
# Installs the grayscale Hyprland rice. Existing configs are moved to ~/.config-backup-<date>/ first.
set -e
here=$(cd "$(dirname "$0")" && pwd)
bak=$HOME/.config-backup-$(date +%Y%m%d-%H%M%S)

if command -v pacman >/dev/null; then
  echo "Installing packages (Arch)..."
  sudo pacman -S --needed - < "$here/packages.txt" || echo "Some packages failed; check packages.txt"
else
  echo "Not Arch: install the packages in packages.txt yourself, then re-run."
fi

for d in "$here"/config/*/; do
  name=$(basename "$d")
  if [ -e "$HOME/.config/$name" ]; then mkdir -p "$bak"; mv "$HOME/.config/$name" "$bak/"; fi
  cp -r "$d" "$HOME/.config/$name"
done
chmod +x "$HOME/.config/i3/scripts/"*.sh "$HOME/.config/i3/scripts/"*.py "$HOME/.config/polybar/scripts/"*.sh

mkdir -p "$HOME/Pictures/Screenshots" "$HOME/.cache"
[ -e "$HOME/Pictures/wall.jpg" ] || cp "$here/wall.jpg" "$HOME/Pictures/wall.jpg"

# configs that can't expand $HOME: point the hard-coded /home/noahd paths at this user
grep -rIl "/home/noahd" "$HOME/.config" 2>/dev/null | xargs -r sed -i "s#/home/noahd#$HOME#g"

# blurred grayscale lock-screen background
magick "$HOME/Pictures/wall.jpg" -resize 1920x1080^ -gravity center -extent 1920x1080 -blur 0x12 \
  -colorspace Gray -fill '#0a0a0a' -colorize 45% -colorspace sRGB "$HOME/.cache/lock-blur.png" || true

echo "Done. Log out and pick Hyprland (needs 0.57+, the config is Lua). Press Super+F1 for the keybind cheatsheet."
[ -d "$bak" ] && echo "Your old configs are in $bak"
