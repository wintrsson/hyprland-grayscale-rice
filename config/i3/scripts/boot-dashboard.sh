#!/usr/bin/env bash
# Runs once at login (see the exec line in ~/.config/i3/config):
#   1. a glitchy full-screen boot splash plays (any key skips it),
#   2. the dashboard builds behind it on workspace 1,
#   3. when the splash ends, the dashboard is simply there (no flicker).
# To turn the animation off but keep the dashboard:   touch ~/.config/i3/no-boot-anim
# To go back to a normal start:                      delete the "boot-dashboard.sh" line in ~/.config/i3/config
FLAG=~/.config/i3/no-boot-anim
HERE=~/.config/i3/scripts

# Hold notifications until the boot sequence is over (dunst queues them and shows them afterwards).
hold_notifs() { for _ in $(seq 20); do dunstctl set-paused true 2>/dev/null && return; sleep 0.25; done; }
hypr=${HYPRLAND_INSTANCE_SIGNATURE:+1}
bar_hidden=""
bar_hide() { if [ -n "$hypr" ]; then
    # wait until waybar has created its bar (SIGUSR1 before its signal handler exists would kill it)
    for _ in $(seq 40); do hyprctl layers -j 2>/dev/null | grep -q '"namespace": "waybar"' && break; sleep 0.25; done
    sleep 0.3; pkill -SIGUSR1 -x waybar && bar_hidden=1; else polybar-msg cmd hide >/dev/null 2>&1; fi; }
bar_show() { if [ -n "$hypr" ]; then [ -n "$bar_hidden" ] && pkill -SIGUSR1 -x waybar; bar_hidden=""; else polybar-msg cmd show >/dev/null 2>&1; fi; }
wm_ws1()   { if [ -n "$hypr" ]; then hyprctl dispatch 'hl.dsp.focus({ workspace = 1 })' >/dev/null; else i3-msg 'workspace number 1' >/dev/null; fi; }
wm_splash_focus() { if [ -n "$hypr" ]; then hyprctl dispatch 'hl.dsp.focus({ window = "class:^bootsplash$" })' >/dev/null 2>&1; else i3-msg '[class="^bootsplash$"] focus' >/dev/null 2>&1; fi; }
dash_open() { if [ -n "$hypr" ]; then hyprctl clients -j | grep -q '"class": "dash-'; else i3-msg -t get_tree | grep -q '"class":"dash-'; fi; }
release_notifs() { dunstctl set-paused false 2>/dev/null; bar_show; }
trap release_notifs EXIT
hold_notifs
bar_hide   # bar + tray also stay out of the way until the splash is done

sleep "${BOOT_DELAY:-0.5}"   # let picom and the bar settle first
if dash_open; then
  if [ -n "$hypr" ]; then pkill -f 'alacritty --class [d]ash-'; pkill -f 'feh .*class [d]ash-art'; else i3-msg '[class="^dash-"] kill' >/dev/null; fi
  sleep 1
fi
wm_ws1

if [ -e "$FLAG" ]; then
  "$HERE/dashboard.sh"
  release_notifs
  setsid "$HERE/term-session.py" auto >/dev/null 2>&1 &
  exit 0
fi

alacritty --class bootsplash -o window.opacity=1.0 -o font.size=12 -e timeout 25 python3 -I "$HERE/boot-anim.py" &
splash=$!

sleep 0.2
"$HERE/dashboard.sh"                                  # panes are built behind the splash
wm_splash_focus      # keep keyboard focus on the splash so a key press skips it
setsid "$HERE/term-session.py" auto >/dev/null 2>&1 &   # reopen last session's terminals now, hidden under the splash, then keep saving them

# Keep the splash on top of every other window (windows that map during boot would otherwise cover it).
while kill -0 "$splash" 2>/dev/null; do
  wm_splash_focus
  sleep 0.1
done
wait "$splash"
release_notifs
