#!/usr/bin/env bash
# Hold-to-seek for the current player: seek.sh fwd | back.  Called repeatedly while a key is held (X key repeat);
# throttled to ~8 steps/s and it accelerates the longer you hold (3 s per step growing to 20 s).
dir=$1; st=/tmp/seek-state
now=$(date +%s.%N); { read -r last n < "$st"; } 2>/dev/null; last=${last:-0}; n=${n:-0}
gap=$(awk -v a="$now" -v b="$last" 'BEGIN{print a-b}')
if awk -v g="$gap" 'BEGIN{exit !(g > 0.8)}'; then n=0; fi            # a new press, not a held key
awk -v g="$gap" 'BEGIN{exit !(g < 0.12)}' && exit 0                  # too soon: skip (rate limit)
step=$(awk -v n="$n" 'BEGIN{s=3+n*0.7; if(s>20)s=20; printf "%.1f", s}')
echo "$now $((n + 1))" > "$st"
case $dir in fwd) playerctl position "${step}+" ;; back) playerctl position "${step}-" ;; esac 2>/dev/null
