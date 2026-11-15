# Grayscale Hyprland rice

Monochrome Hyprland setup: waybar, a boot splash and dashboard on workspace 1
(album art, cava visualizer, btop, weather, fastfetch), rounded windows with blur,
and a lock screen to match.

![desktop](screenshots/desktop.jpg)

**Needs Hyprland 0.57 or newer** (the config is `hyprland.lua`). Written for Arch.

    git clone <this repo> && cd dotfiles && ./install.sh

The installer backs up any config it replaces. After logging in, `Super+F1` shows every keybind.

Notes
- The dashboard's Docker and Tailscale panes just show `n/a` if you don't run them.
- Spotify is autostarted on workspace 9 (`spotify-launcher`) and `Super+M` opens `spotify_player`;
  delete those lines in `config/hypr/hyprland.lua` if you don't use them.
- The wallpaper is `wall.jpg`; replace `~/Pictures/wall.jpg` with your own and the lock screen follows.
- Cava shader files keep their original authors' license headers.
