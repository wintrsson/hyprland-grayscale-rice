#!/usr/bin/env python3
"""Render the dashboard weather pane from wttr.in's cached JSON. Usage: weather-render.py CACHE COLS"""
import json
import sys
from datetime import datetime

cache, cols = sys.argv[1], int(sys.argv[2])
B, D, R = "\033[1m", "\033[2m", "\033[0m"


def cut(s, n):
    return s if len(s) <= n else s[: max(n - 1, 1)] + "…"


def header(title, right=""):
    right = cut(right, max(cols - len(title) - 6, 0))
    pad = max(cols - len(title) - len(right) - 2, 1)
    return [f" {B}{title}{R}{' ' * pad}{D}{right}{R}", f" {D}{'─' * (cols - 2)}{R}"]


try:
    d = json.load(open(cache))
    cur = d["current_condition"][0]
    area = d["nearest_area"][0]["areaName"][0]["value"]
except Exception:
    print("\n".join(header("weather", "offline")) + f"\n\n {D}no data yet{R}", end="")
    sys.exit(0)

lines = header("weather", area)
lines.append("")
lines.append(f" {B}{cur['temp_F']}°F{R}  {cut(cur['weatherDesc'][0]['value'], cols - 10)}")
lines.append(f" {D}feels {cur['FeelsLikeF']}°  humidity {cur['humidity']}%{R}")
lines.append(f" {D}wind {cur['windspeedMiles']} mph {cur['winddir16Point']}   uv {cur['uvIndex']}{R}")
lines.append("")

for i, day in enumerate(d["weather"][:3]):
    name = "today" if i == 0 else datetime.strptime(day["date"], "%Y-%m-%d").strftime("%a").lower()
    # midday description and the day's highest chance of rain
    desc = day["hourly"][4]["weatherDesc"][0]["value"]
    rain = max(int(h["chanceofrain"]) for h in day["hourly"])
    temps = f"{day['maxtempF']}°/{day['mintempF']}°"
    head = f" {B}{name:<5}{R} {temps:<8}"
    room = cols - 2 - 6 - 9
    tail = cut(desc, room)
    lines.append(head + tail)
    if rain >= 20:
        lines.append(f" {D}{' ' * 6}{rain}% chance of rain{R}")

print("\n".join(lines), end="")
