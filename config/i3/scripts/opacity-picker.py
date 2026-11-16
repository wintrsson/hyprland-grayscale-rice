#!/usr/bin/env python3
"""Window opacity popup (Super+O). Three sliders, applied live:
  Terminals & dashboard  -> alacritty's own background opacity (text stays sharp), saved in ~/.config/alacritty/alacritty.toml
  Other windows          -> Hyprland active_opacity (the whole window), saved in ~/.config/hypr/opacity.conf
  Dim unfocused windows  -> Hyprland inactive_opacity = other-windows x this factor (100% = no extra dimming), same file"""
import os, re, subprocess, sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget)

HOME = os.path.expanduser("~")
TOML = HOME + "/.config/alacritty/alacritty.toml"
CONF = HOME + "/.config/hypr/opacity.conf"
DEFAULTS = {"terminal": 78, "windows": 100, "dim": 100}
PRESETS = [("Solid", {"terminal": 100, "windows": 100, "dim": 100}), ("Default", DEFAULTS),
           ("Glass", {"terminal": 55, "windows": 92, "dim": 92}), ("Ghost", {"terminal": 35, "windows": 80, "dim": 85})]

STYLE = """
* { font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 13px; color: #d4d4d4; }
QWidget#root { background: #141414; }
QLabel#title { font-size: 22px; font-weight: bold; color: #ffffff; }
QLabel#hint { color: #8a8a8a; }
QLabel#value { color: #ffffff; font-weight: bold; min-width: 52px; }
QLabel#section { font-weight: bold; color: #ffffff; font-size: 14px; }
QFrame#card { background: #1c1c1c; border: 1px solid #2a2a2a; border-radius: 12px; }
QPushButton { background: #232323; border: 1px solid #333333; border-radius: 9px; padding: 8px 16px; }
QPushButton:hover { background: #2e2e2e; border-color: #4a4a4a; }
QPushButton#primary { background: #e6e6e6; color: #111111; border: 1px solid #e6e6e6; font-weight: bold; }
QPushButton#primary:hover { background: #ffffff; }
QSlider::groove:horizontal { height: 6px; background: #333333; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #d8d8d8; border-radius: 3px; }
QSlider::handle:horizontal { background: #ffffff; width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; }
QSlider::handle:horizontal:hover { background: #cfcfcf; }
"""


def get_terminal():
    try:
        m = re.search(r"^opacity\s*=\s*([0-9.]+)", open(TOML).read(), re.M)
        return round(float(m.group(1)) * 100)
    except Exception:
        return DEFAULTS["terminal"]


def get_hypr():
    vals = {"windows": 1.0, "inactive": 1.0}
    try:
        for k, v in re.findall(r"(\w+)=([0-9.]+)", open(CONF).read()):
            if k in vals:
                vals[k] = float(v)
    except OSError:
        pass
    return {"windows": round(vals["windows"] * 100), "dim": round(min(1.0, vals["inactive"] / max(vals["windows"], 0.01)) * 100)}


def set_terminal(pct):
    """alacritty reloads its config file by itself, so every open terminal follows at once"""
    try:
        s = open(TOML).read()
        s2 = re.sub(r"^(opacity\s*=\s*)[0-9.]+", lambda m: f"{m.group(1)}{pct / 100:.2f}", s, count=1, flags=re.M)
        if s2 != s:
            open(TOML, "w").write(s2)
    except OSError:
        pass


def set_hypr(windows, dim):
    w = windows / 100
    i = w * dim / 100                       # unfocused windows are never more solid than focused ones
    subprocess.run(["hyprctl", "eval", f"hl.config({{ decoration = {{ active_opacity = {w:.2f}, inactive_opacity = {i:.2f} }} }})"],
                   capture_output=True)
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    open(CONF, "w").write(f"windows={w:.2f}\ninactive={i:.2f}\n")


class Popup(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("Window opacity")
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 22)
        v.setSpacing(12)
        t = QLabel("Window opacity")
        t.setObjectName("title")
        s = QLabel("Changes apply as you drag.")
        s.setObjectName("hint")
        v.addWidget(t)
        v.addWidget(s)
        self.sliders = {}
        cur = {"terminal": get_terminal(), **get_hypr()}
        rows = [("terminal", "Terminals & dashboard", "The see-through look of terminals and the dashboard panes. Text stays sharp.", 10),
                ("windows", "Other windows", "Browser, Spotify and other apps (the whole window fades).", 40),
                ("dim", "Dim unfocused windows", "Extra fade for windows that don't have focus (100% = none). Terminals are not affected.", 40)]
        for key, name, hint, lo in rows:
            card = QFrame()
            card.setObjectName("card")
            cv = QVBoxLayout(card)
            cv.setContentsMargins(20, 14, 20, 14)
            cv.setSpacing(6)
            top = QHBoxLayout()
            lab = QLabel(name)
            lab.setObjectName("section")
            val = QLabel()
            val.setObjectName("value")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            top.addWidget(lab)
            top.addStretch()
            top.addWidget(val)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(lo, 100)
            sl.setValue(max(lo, min(100, cur[key])))
            h = QLabel(hint)
            h.setObjectName("hint")
            h.setWordWrap(True)
            cv.addLayout(top)
            cv.addWidget(sl)
            cv.addWidget(h)
            v.addWidget(card)
            self.sliders[key] = (sl, val)
            sl.valueChanged.connect(self.changed)
        v.addStretch()
        foot = QHBoxLayout()
        for name, vals in PRESETS:
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, vals=vals: self.preset(vals))
            foot.addWidget(b)
        foot.addStretch()
        done = QPushButton("Close")
        done.setObjectName("primary")
        done.clicked.connect(self.close)
        foot.addWidget(done)
        v.addLayout(foot)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.apply)
        self.show_values()

    def show_values(self):
        for sl, val in self.sliders.values():
            val.setText(f"{sl.value()}%")

    def changed(self, *_):
        self.show_values()
        self.timer.start(60)                       # apply shortly after the last movement

    def preset(self, vals):
        for k, (sl, _) in self.sliders.items():
            sl.blockSignals(True)
            sl.setValue(max(sl.minimum(), vals[k]))
            sl.blockSignals(False)
        self.show_values()
        self.apply()

    def apply(self):
        set_terminal(self.sliders["terminal"][0].value())
        set_hypr(self.sliders["windows"][0].value(), self.sliders["dim"][0].value())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setDesktopFileName("opacitypicker")
    app.setStyleSheet(STYLE)
    w = Popup()
    w.resize(700, 530)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
