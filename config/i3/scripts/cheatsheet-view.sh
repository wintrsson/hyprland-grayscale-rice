#!/usr/bin/env bash
# Shows the keybinds page and closes on q, Esc, Enter or Space (plain `less` only quits on q).
clear; cat ~/.config/i3/cheatsheet.txt; printf '\033[?25l'
while IFS= read -rsn1 k; do case $k in q|$'\e'|' '|'') break ;; esac; done
