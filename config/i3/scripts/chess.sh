#!/usr/bin/env bash
# Chess button: chess.com as a standalone app window (own Firefox profile, no tabs/toolbar) on a new empty workspace.
# --- Hyprland session: waybar pawn (fifo) + hyprctl ---
if [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ]; then
  ( timeout 1 sh -c 'echo hop > /tmp/pawn-ctl' ) &
  if hyprctl clients -j | jq -e '.[] | select(.class=="chesscom")' >/dev/null 2>&1; then
    hyprctl dispatch 'hl.dsp.focus({ window = "class:^chesscom$" })' >/dev/null; exit 0
  fi
  # open on the lowest-numbered workspace that has no windows
  used=$(hyprctl workspaces -j | jq -r '.[]|select(.windows>0)|.id')
  n=1; while echo "$used" | grep -qx "$n"; do n=$((n+1)); done
  hyprctl dispatch "hl.dsp.focus({ workspace = $n })" >/dev/null
  setsid firefox --no-remote --class chesscom --name chesscom -P chesscom --new-window https://www.chess.com/home >/dev/null 2>&1 &
  exit 0
fi
# pawn hop animation on the bar button (polybar ipc module "chess": hook 0 = rest, hooks 1-8 = height of the hop)
( for h in 1 2 4 6 6 5 3 2 1 0 1 0; do polybar-msg action "#chess.hook.$h" >/dev/null 2>&1; sleep 0.032; done; polybar-msg action "#chess.hook.0" >/dev/null 2>&1 ) &
if i3-msg '[class="chesscom"] focus' 2>/dev/null | grep -q '"success":true'; then exit 0; fi
i3-msg 'workspace number 2' >/dev/null
exec firefox --no-remote --class chesscom --name chesscom -P chesscom --new-window https://www.chess.com/home
