#!/usr/bin/env bash
# Dashboard "services" pane: Docker containers + Tailscale devices. Refreshes every 10 seconds.
# Shows names and up/down status only. Running items first, stopped ones dimmed at the bottom.
B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'; W=$'\033[97m'

cols() { local c; c=$(stty size </dev/tty 2>/dev/null | awk '{print $2}'); echo "${c:-30}"; }
trap : WINCH   # redraw right away when the pane is resized

# section header: bold title on the left, count on the right, then a thin dim divider
header() {
  local title=$1 count=$2 c; c=$(cols)
  local pad=$(( c - ${#title} - ${#count} - 2 )); [ "$pad" -lt 1 ] && pad=1
  printf ' %s%s%s%*s%s%s%s\n' "$B" "$title" "$R" "$pad" "" "$D" "$count" "$R"
  printf ' %s%s%s\n' "$D" "$(printf '─%.0s' $(seq 1 $(( c - 2 ))))" "$R"
}

# one row: status dot + name (cut to fit the pane, never wraps); $3 is an optional trailing mark
row() {
  local up=$1 name=$2 mark=$3 c max; c=$(cols); max=$(( c - 6 ))
  [ ${#name} -gt "$max" ] && name="${name:0:$(( max - 1 ))}…"
  if [ "$up" = 1 ]; then
    printf ' %s●%s %s%s%s\n' "$W" "$R" "$name" "${mark:+ $B$mark$R}" ""
  else
    printf ' %s○ %s%s\n' "$D" "$name" "$R"
  fi
}

while :; do
  out=""

  # ---- docker ----
  list=$(docker ps -a --format '{{.Names}}|{{.State}}|{{.Status}}' 2>/dev/null | sort)
  if [ -z "$list" ]; then
    out+="$(header docker 'n/a')"$'\n'
  else
    total=$(printf '%s\n' "$list" | wc -l)
    up=$(printf '%s\n' "$list" | awk -F'|' '$2=="running"' | wc -l)
    out+="$(header docker "$up/$total")"$'\n'
    # running first, then stopped
    while IFS='|' read -r name state status; do
      [ "$state" = running ] || continue
      mark=""; case $status in *unhealthy*) mark='!' ;; esac
      out+="$(row 1 "$name" "$mark")"$'\n'
    done <<< "$list"
    while IFS='|' read -r name state status; do
      [ "$state" = running ] && continue
      out+="$(row 0 "$name")"$'\n'
    done <<< "$list"
  fi

  # ---- tailscale ----
  out+=$'\n'
  if command -v tailscale >/dev/null 2>&1; then
    ts=$(tailscale status 2>/dev/null | awk 'NF>=2 && $1 ~ /^[0-9]/ { off = ($0 ~ /offline/); printf "%s|%s\n", off ? "0" : "1", $2 }')
    if [ -n "$ts" ]; then
      n_on=$(printf '%s\n' "$ts" | grep -c '^1|')
      n_all=$(printf '%s\n' "$ts" | wc -l)
      out+="$(header tailscale "$n_on/$n_all")"$'\n'
      while IFS='|' read -r on name; do
        name=${name%-wificellular}   # display name only; the device itself is not renamed
        [ "$on" = 1 ] && out+="$(row 1 "$name")"$'\n'
      done <<< "$ts"
      while IFS='|' read -r on name; do
        name=${name%-wificellular}
        [ "$on" = 1 ] || out+="$(row 0 "$name")"$'\n'
      done <<< "$ts"
    else
      out+="$(header tailscale 'off')"$'\n'
    fi
  fi

  printf '\033[H\033[J\033[?25l%s' "${out%$'\n'}"
  sleep 10 & wait $!   # interruptible, so a resize redraws immediately
done
