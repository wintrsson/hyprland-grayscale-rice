-- Hyprland config (Lua) — ported from the i3 rice: monochrome, 12px radius, 14px gaps. i3 stays available as its own session.
-- Phase 1: core desktop. Dashboard / boot splash / terminal restore are ported separately.

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "1" })

local mod  = "SUPER"
local term = "env GTK_THEME=Breeze:dark QT_QPA_PLATFORMTHEME=kde alacritty"
local ds   = "~/.config/i3/scripts/"

-- alacritty font/padding for Wayland (X11 scaled text by ~1.48; see ~/.config/alacritty/alacritty.toml)
os.execute("ln -sf session-wl.toml ~/.config/alacritty/session.toml")

-- Run on the Intel iGPU (it drives the laptop screen); the NVIDIA card stays free for offload.
-- (The list separator is ":", so the by-path name with colons can't be used directly: resolve it to /dev/dri/cardN here.)
local intel = "/dev/dri/card2"
local h = io.popen("readlink -f /dev/dri/by-path/pci-0000:00:02.0-card 2>/dev/null")
if h then
    local r = h:read("*l"); h:close()
    if r and r:match("^/dev/dri/card%d+$") then intel = r end
end
hl.env("AQ_DRM_DEVICES", intel)
hl.env("XCURSOR_SIZE", "24")
hl.env("GTK_THEME", "Breeze:dark")
hl.env("QT_QPA_PLATFORMTHEME", "kde")
hl.env("MOZ_ENABLE_WAYLAND", "1")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")

-- ---------------------------------------------------------------- look
hl.config({
    general = {
        gaps_in = 7,
        gaps_out = 18,
        border_size = 2,
        col = { active_border = "rgb(333333)", inactive_border = "rgb(1e1e1e)" },
        resize_on_border = false,
        layout = "dwindle",
    },
    decoration = {
        rounding = 12,
        active_opacity = 1.0,
        inactive_opacity = 1.0,
        blur = { enabled = true, size = 8, passes = 3, noise = 0.0, contrast = 0.9, brightness = 0.8 },
        shadow = { enabled = true, range = 22, render_power = 3, color = 0x8c000000, offset = "-14 -12" },
    },
    animations = { enabled = true },
    dwindle = { preserve_split = true },      -- replaces the autotiling script
    misc = {
        disable_hyprland_logo = true,
        force_default_wallpaper = 0,
        background_color = 0xff0a0a0a,
    },
    binds = { workspace_back_and_forth = true },   -- i3 workspace_auto_back_and_forth
    input = { follow_mouse = 0, touchpad = { natural_scroll = false } },
    cursor = { inactive_timeout = 1, no_warps = true },             -- hide the cursor after 1 s
})

hl.curve("quick", { type = "bezier", points = { {0.15, 0}, {0.1, 1} } })
hl.animation({ leaf = "windows",    enabled = true, speed = 3, bezier = "quick", style = "popin 94%" })
hl.animation({ leaf = "fade",       enabled = true, speed = 3, bezier = "quick" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 3, bezier = "quick", style = "fade" })
hl.animation({ leaf = "layers",     enabled = true, speed = 3, bezier = "quick", style = "fade" })

-- ---------------------------------------------------------------- autostart
hl.on("hyprland.start", function()
    hl.exec_cmd("hyprpaper")
    hl.exec_cmd(ds .. "parallax.py")           -- wallpaper daemon: moves with the mouse, rotates, crossfades
    hl.exec_cmd("waybar")
    hl.exec_cmd("dunst")
    hl.exec_cmd("hypridle")
    hl.exec_cmd(ds .. "track-notify.sh")
    hl.exec_cmd("alacritty --class dropterm", { workspace = "special:dropterm silent" })
    hl.exec_cmd("spotify-launcher", { workspace = "9 silent" })
    hl.exec_cmd(ds .. "overflow-hypr.py")      -- new windows on workspace 1 get their own workspace
    hl.exec_cmd(ds .. "keep-hypr-log.sh")      -- keeps the last lines of the Hyprland log across reboots (crash diagnosis)
    hl.exec_cmd(ds .. "boot-dashboard.sh")     -- boot splash + dashboard + terminal restore
end)

-- ---------------------------------------------------------------- window rules
hl.window_rule({ name = "dropterm", match = { class = "^dropterm$" }, float = true, size = "1100 600", center = true })
hl.window_rule({ name = "floaters", match = { class = "^(Pavucontrol|pavucontrol|Nm-connection-editor|Blueman-manager|Lxappearance)$" }, float = true })
hl.window_rule({ name = "spotui", match = { class = "^spotui$" }, float = true, size = "1200 720", center = true })
hl.window_rule({ name = "cheatsheet", match = { class = "^cheatsheet$" }, float = true, size = "1560 900", center = true })
hl.window_rule({ name = "bttui",  match = { class = "^bttui$" },  float = true, size = "900 520",  center = true })
hl.window_rule({ name = "wifitui", match = { class = "^wifitui$" }, float = true, size = "700 520", center = true })
hl.window_rule({ name = "wallpaperpicker", match = { class = "^wallpaperpicker$" }, float = true, size = "1180 780", center = true })
hl.window_rule({ name = "audiotui", match = { class = "^audiotui$" }, float = true, size = "900 440", center = true })
hl.window_rule({ name = "spotify", match = { class = "^(Spotify|spotify)$" }, workspace = "9 silent" })
hl.window_rule({ name = "cavaterm", match = { class = "^cavaterm$" }, float = true, pin = true, size = "720 200" })
hl.window_rule({ name = "video-opaque", match = { class = "^(mpv|Jellyfin Media Player)$" }, opaque = true })
hl.window_rule({ name = "suppress-maximize", match = { class = ".*" }, suppress_event = "maximize" })

-- dashboard panes (workspace 1): fixed slots, same geometry as the i3 layout (screen 1920x1080, bar on top)
local function dash(cls, x, y, w, h)
    hl.window_rule({ name = "dash-" .. cls, match = { class = "^dash-" .. cls .. "$" },
        float = true, workspace = "1 silent", move = x .. " " .. y, size = w .. " " .. h,
        no_shadow = true })   -- raised-on-click panes would otherwise cast their shadow onto neighbours
end
dash("art",     18,   58, 572, 680)
dash("fetch",   18,  752, 572, 310)
dash("cava",   604,   58, 942, 288)
dash("btop",   604,  360, 942, 702)
dash("svc",   1560,   58, 342, 618)
dash("weather",1560,  692, 342, 370)

-- boot splash: full screen, above everything
hl.window_rule({ name = "bootsplash", match = { class = "^bootsplash$" }, float = true, size = "1920 1080", move = "0 0", pin = true,
    border_size = 0, rounding = 0, no_shadow = true })

hl.layer_rule({ name = "waybar-blur", match = { namespace = "^waybar$" }, blur = true, ignore_alpha = 0.3 })

-- ---------------------------------------------------------------- keys
hl.bind(mod .. " + Return", hl.dsp.exec_cmd(term))
hl.bind(mod .. " + SHIFT + Q", hl.dsp.window.close())
hl.bind(mod .. " + D", hl.dsp.exec_cmd("env GTK_THEME=Breeze:dark QT_QPA_PLATFORMTHEME=kde rofi -show drun"))
hl.bind(mod .. " + P", hl.dsp.exec_cmd("rofi -show window"))

-- focus / move window (j k l ;  and arrows)
local dirs = { J = "left", K = "down", L = "up", semicolon = "right", left = "left", down = "down", up = "up", right = "right" }
for key, d in pairs(dirs) do
    hl.bind(mod .. " + " .. key,           hl.dsp.focus({ direction = d }))
    hl.bind(mod .. " + SHIFT + " .. key,   hl.dsp.window.move({ direction = d }))
end

-- layout
hl.bind(mod .. " + H", hl.dsp.layout("preselect r"))
hl.bind(mod .. " + V", hl.dsp.layout("preselect d"))
hl.bind(mod .. " + F", hl.dsp.window.fullscreen())
hl.bind(mod .. " + S", hl.dsp.group.toggle())
hl.bind(mod .. " + W", hl.dsp.group.toggle())
hl.bind(mod .. " + E", hl.dsp.layout("togglesplit"))
hl.bind(mod .. " + SHIFT + space", hl.dsp.window.float({ action = "toggle" }))
hl.bind(mod .. " + space", hl.dsp.window.cycle_next())
hl.bind(mod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind(mod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- resize (Super+Ctrl+j k l ;  and arrows)
local rs = { J = {-40, 0}, semicolon = {40, 0}, K = {0, 40}, L = {0, -40}, left = {-40, 0}, right = {40, 0}, down = {0, 40}, up = {0, -40} }
for key, v in pairs(rs) do
    hl.bind(mod .. " + CTRL + " .. key, hl.dsp.window.resize({ x = v[1], y = v[2], relative = true }), { repeating = true })
end

-- workspaces
for i = 1, 10 do
    local key = i % 10
    hl.bind(mod .. " + " .. key,           hl.dsp.focus({ workspace = i }))
    hl.bind(mod .. " + SHIFT + " .. key,   hl.dsp.window.move({ workspace = i }))
end
hl.bind(mod .. " + Tab", hl.dsp.focus({ workspace = "previous" }))

-- hide / show windows (i3 scratchpad) and the drop-down terminal
hl.bind(mod .. " + Z", hl.dsp.window.move({ workspace = "special:hidden", follow = false }))
hl.bind(mod .. " + X", hl.dsp.workspace.toggle_special("hidden"))
hl.bind(mod .. " + grave", hl.dsp.workspace.toggle_special("dropterm"))

-- reload / power menu
hl.bind(mod .. " + SHIFT + C", hl.dsp.exec_cmd("hyprctl reload"))
hl.bind(mod .. " + SHIFT + X", hl.dsp.submap("system"))
hl.define_submap("system", "reset", function()
    hl.bind("L", hl.dsp.exec_cmd("hyprlock"))
    hl.bind("E", hl.dsp.exit())
    hl.bind("S", hl.dsp.exec_cmd("systemctl suspend"))
    hl.bind("R", hl.dsp.exec_cmd("systemctl reboot"))
    hl.bind("P", hl.dsp.exec_cmd("systemctl poweroff"))
    hl.bind("Return", hl.dsp.submap("reset"))
    hl.bind("Escape", hl.dsp.submap("reset"))
end)

-- media / volume / brightness
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd("pactl set-source-mute @DEFAULT_SOURCE@ toggle"), { locked = true })
hl.bind("XF86MonBrightnessUp",  hl.dsp.exec_cmd("brightnessctl set +5%"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown",hl.dsp.exec_cmd("brightnessctl set 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { locked = true })
hl.bind(mod .. " + SHIFT + P", hl.dsp.exec_cmd("playerctl play-pause"))
hl.bind(mod .. " + bracketright", hl.dsp.exec_cmd("playerctl next"))
hl.bind(mod .. " + bracketleft",  hl.dsp.exec_cmd("playerctl previous"))
hl.bind(mod .. " + SHIFT + bracketright", hl.dsp.exec_cmd(ds .. "seek.sh fwd"),  { repeating = true })
hl.bind(mod .. " + SHIFT + bracketleft",  hl.dsp.exec_cmd(ds .. "seek.sh back"), { repeating = true })
hl.bind("SHIFT + XF86AudioNext", hl.dsp.exec_cmd(ds .. "seek.sh fwd"),  { locked = true, repeating = true })
hl.bind("SHIFT + XF86AudioPrev", hl.dsp.exec_cmd(ds .. "seek.sh back"), { locked = true, repeating = true })

-- screenshots
hl.bind("Print",         hl.dsp.exec_cmd("mkdir -p ~/Pictures/Screenshots && grim ~/Pictures/Screenshots/$(date +%F_%H-%M-%S).png && notify-send 'Screenshot saved'"))
hl.bind("SHIFT + Print", hl.dsp.exec_cmd("grim -g \"$(slurp)\" - | wl-copy && notify-send 'Region copied'"))

-- my tools
hl.bind(mod .. " + SHIFT + A", hl.dsp.exec_cmd(ds .. "airpods.sh"))
hl.bind(mod .. " + SHIFT + I", hl.dsp.exec_cmd(ds .. "show-ip.sh"))
hl.bind(mod .. " + M", hl.dsp.exec_cmd(ds .. "toggle-tui.sh spotui /home/noahd/.local/bin/spotify_player"))
hl.bind(mod .. " + B", hl.dsp.exec_cmd(ds .. "toggle-tui.sh bttui bluetui"))
hl.bind(mod .. " + N", hl.dsp.exec_cmd(ds .. "toggle-tui.sh wifitui " .. ds .. "wifi-tui.py"))
hl.bind(mod .. " + A", hl.dsp.exec_cmd(ds .. "toggle-tui.sh audiotui " .. ds .. "audio-tui.py"))
hl.bind(mod .. " + SHIFT + W", hl.dsp.exec_cmd(ds .. "wallpaper.sh next"))
hl.bind(mod .. " + CTRL + W", hl.dsp.exec_cmd(ds .. "wallpaper-picker.sh"))
hl.bind(mod .. " + SHIFT + D", hl.dsp.exec_cmd(ds .. "dashboard.sh"))
hl.bind(mod .. " + SHIFT + B", hl.dsp.exec_cmd("env BOOT_DELAY=0 " .. ds .. "boot-dashboard.sh"))
hl.bind(mod .. " + SHIFT + S", hl.dsp.exec_cmd(ds .. "term-session.py save"))
hl.bind(mod .. " + SHIFT + T", hl.dsp.exec_cmd(ds .. "term-session.py restore"))
hl.bind(mod .. " + C", hl.dsp.exec_cmd(ds .. "toggle-cava.sh"))
hl.bind(mod .. " + F1", hl.dsp.exec_cmd(ds .. "cheatsheet.sh"))
