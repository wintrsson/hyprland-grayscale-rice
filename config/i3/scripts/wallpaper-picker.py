#!/usr/bin/env python3
"""Wallpaper chooser (Super+Ctrl+W). Screen 1: pick the pictures. Screen 2: how they should change (order, how often,
parallax, per-workspace, lock screen). Writes ~/.config/hypr/wallpaper.json and tells the wallpaper daemon (parallax.py)."""
import glob, hashlib, json, os, subprocess, sys

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QImage, QImageReader, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QListView, QListWidget, QListWidgetItem, QPushButton, QRadioButton, QStackedWidget, QVBoxLayout,
                               QWidget)

HOME = os.path.expanduser("~")
CFG = HOME + "/.config/hypr/wallpaper.json"
CACHE = HOME + "/.cache/parallax"
THUMBS = CACHE + "/thumbs"
TW, TH = 232, 131
EXTS = ("jpg", "jpeg", "png", "webp")

STYLE = """
* { font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 13px; color: #d4d4d4; }
QWidget#root { background: #141414; }
QLabel#title { font-size: 22px; font-weight: bold; color: #ffffff; }
QLabel#sub, QLabel#hint { color: #8a8a8a; }
QLabel#count { color: #ffffff; font-weight: bold; }
QLabel#status { color: #ffffff; }
QFrame#card { background: #1c1c1c; border: 1px solid #2a2a2a; border-radius: 12px; }
QLabel#section { font-weight: bold; color: #ffffff; font-size: 14px; }
QListWidget { background: #181818; border: 1px solid #2a2a2a; border-radius: 12px; padding: 8px; outline: 0; }
QListWidget::item { border: none; padding: 2px; }
QListWidget::item:selected, QListWidget::item:hover { background: transparent; }
QPushButton { background: #232323; border: 1px solid #333333; border-radius: 9px; padding: 8px 18px; }
QPushButton:hover { background: #2e2e2e; border-color: #4a4a4a; }
QPushButton:disabled { color: #5a5a5a; background: #1a1a1a; border-color: #262626; }
QPushButton#primary { background: #e6e6e6; color: #111111; border: 1px solid #e6e6e6; font-weight: bold; }
QPushButton#primary:hover { background: #ffffff; }
QPushButton#primary:disabled { background: #3a3a3a; color: #777777; border-color: #3a3a3a; }
QRadioButton, QCheckBox { spacing: 10px; padding: 3px 0; }
QRadioButton::indicator, QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #5a5a5a; background: #141414; }
QRadioButton::indicator { border-radius: 9px; }
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator:checked, QCheckBox::indicator:checked { background: #e6e6e6; border: 1px solid #e6e6e6; }
QRadioButton::indicator:disabled, QCheckBox::indicator:disabled { border-color: #333333; background: #1a1a1a; }
QCheckBox:disabled, QRadioButton:disabled { color: #5a5a5a; }
QComboBox { background: #232323; border: 1px solid #333333; border-radius: 8px; padding: 6px 12px; min-width: 150px; }
QComboBox:disabled { color: #5a5a5a; }
QComboBox::drop-down { border: none; width: 28px; background: transparent; }
QComboBox::down-arrow { image: url(ARROW); width: 14px; height: 10px; }
QCheckBox::indicator:checked { image: url(CHECK); }
QComboBox QAbstractItemView { background: #1c1c1c; border: 1px solid #333333; selection-background-color: #3a3a3a; outline: 0; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #3a3a3a; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

ORDERS = [("shuffle", "Shuffle", "Every picture once in a random order, then a new round (never the same one twice in a row)"),
          ("sequential", "In order", "One after another, sorted by name"),
          ("random", "Random", "A random picture each time (the same one can come back sooner)"),
          ("single", "Just one", "Keep the first picture you selected and never change")]
INTERVALS = [("Never", 0), ("Every 5 minutes", 5), ("Every 15 minutes", 15), ("Every 30 minutes", 30), ("Every hour", 60),
             ("Every 3 hours", 180), ("Every 6 hours", 360), ("Once a day", 1440)]
AMOUNTS = [("Subtle", "subtle"), ("Medium", "medium"), ("Strong", "strong")]


def make_icons():
    """small PNGs for the combo-box arrow and the checkbox tick (Qt style sheets need image files)"""
    from PySide6.QtGui import QPainter, QPen, QPixmap
    os.makedirs(CACHE, exist_ok=True)
    pm = QPixmap(14, 10)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#9a9a9a"), 2))
    p.drawLine(2, 2, 7, 7)
    p.drawLine(7, 7, 12, 2)
    p.end()
    pm.save(CACHE + "/arrow.png")
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#111111"), 2.4))
    p.drawLine(3, 8, 7, 12)
    p.drawLine(7, 12, 13, 4)
    p.end()
    pm.save(CACHE + "/check.png")


def load_cfg():
    cfg = {"list": [], "order": "shuffle", "interval": 30, "on_login": False, "parallax": True,
           "parallax_amount": "medium", "per_workspace": False, "lock_follows": True}
    try:
        cfg.update(json.load(open(CFG)))
    except (OSError, ValueError):
        pass
    return cfg


def candidates(cfg):
    found = []
    for e in EXTS:
        found += glob.glob(f"{HOME}/Pictures/wall.*.{e}")
        found += glob.glob(f"{HOME}/Pictures/wallpapers/*.{e}")
    found += [p for p in cfg.get("list", []) if os.path.exists(p)]
    return sorted(set(found), key=lambda p: os.path.basename(p).lower())


def thumb(path):
    os.makedirs(THUMBS, exist_ok=True)
    st = os.stat(path)
    cp = f"{THUMBS}/{hashlib.md5(f'{path}{st.st_mtime_ns}'.encode()).hexdigest()[:16]}.png"
    if os.path.exists(cp):
        img = QImage(cp)
        if not img.isNull():
            return QPixmap.fromImage(img)
    r = QImageReader(path)
    r.setAutoTransform(True)
    size = r.size()
    if size.isValid():
        s = size.scaled(TW * 2, TH * 2, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        r.setScaledSize(s)
    img = r.read()
    if img.isNull():
        img = QImage(TW, TH, QImage.Format.Format_RGB32)
        img.fill(QColor("#222222"))
    img = img.scaled(TW, TH, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    x, y = (img.width() - TW) // 2, (img.height() - TH) // 2
    img = img.copy(x, y, TW, TH)
    img.save(cp)
    return QPixmap.fromImage(img)


def tile(base, selected, small):
    """thumbnail with a clear on/off look: selected = bright with a white frame and tick, off = dimmed"""
    pm = QPixmap(base)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if not selected:
        p.fillRect(pm.rect(), QColor(0, 0, 0, 150))
    else:
        p.setPen(QPen(QColor("#ffffff"), 4))
        p.drawRect(pm.rect().adjusted(2, 2, -2, -2))
        p.setBrush(QColor("#ffffff"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(pm.width() - 36, 10, 26, 26)
        p.setPen(QPen(QColor("#111111"), 3))
        p.drawLine(pm.width() - 30, 24, pm.width() - 25, 29)
        p.drawLine(pm.width() - 25, 29, pm.width() - 16, 17)
    if small:
        p.setPen(QColor("#ffffff"))
        p.setFont(QFont("JetBrainsMono Nerd Font", 9))
        p.fillRect(8, pm.height() - 26, 150, 20, QColor(0, 0, 0, 170))
        p.drawText(14, pm.height() - 11, "low resolution")
    p.end()
    return QIcon(pm)


class Grid(QListWidget):
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space and self.currentItem():
            self.window().toggle(self.currentItem())
            return
        super().keyPressEvent(e)


class Picker(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("Wallpapers")
        self.cfg = load_cfg()
        self.paths = candidates(self.cfg)
        sel = set(self.cfg.get("list", []))
        self.sel = {p: (p in sel) for p in self.paths}
        self.bases = {}
        self.small = {}

        self.stack = QStackedWidget()
        self.stack.addWidget(self.page_pick())
        self.stack.addWidget(self.page_settings())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.addWidget(self.stack)
        self.load_timer = QTimer(self)
        self.load_timer.timeout.connect(self.load_some)
        self.queue = list(range(len(self.paths)))
        self.load_timer.start(5)
        self.refresh_count()

    # -------------------------------------------------------------- page 1
    def page_pick(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        head = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("Choose your wallpapers")
        t.setObjectName("title")
        s = QLabel("Click a picture to switch it on or off. Step 1 of 2")
        s.setObjectName("sub")
        col.addWidget(t)
        col.addWidget(s)
        head.addLayout(col)
        head.addStretch()
        self.count = QLabel()
        self.count.setObjectName("count")
        head.addWidget(self.count)
        v.addLayout(head)
        bar = QHBoxLayout()
        for text, fn in (("Select all", lambda: self.set_all(True)), ("Select none", lambda: self.set_all(False)),
                         ("Invert", self.invert), ("Add pictures…", self.add_pictures)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch()
        v.addLayout(bar)
        self.grid = Grid()
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setIconSize(QSize(TW, TH))
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setSpacing(8)
        self.grid.setUniformItemSizes(True)
        self.grid.setWordWrap(True)
        self.grid.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for p in self.paths:
            it = QListWidgetItem(os.path.basename(p).removeprefix("wall.").rsplit(".", 1)[0])
            it.setData(Qt.ItemDataRole.UserRole, p)
            it.setSizeHint(QSize(TW + 12, TH + 34))
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.grid.addItem(it)
        self.grid.itemClicked.connect(self.toggle)
        v.addWidget(self.grid, 1)
        foot = QHBoxLayout()
        self.warn = QLabel("")
        self.warn.setObjectName("hint")
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.close)
        self.next_btn = QPushButton("Next  →")
        self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self.go_settings)
        foot.addWidget(self.warn)
        foot.addStretch()
        foot.addWidget(cancel)
        foot.addWidget(self.next_btn)
        v.addLayout(foot)
        return w

    def load_some(self):
        for _ in range(3):
            if not self.queue:
                self.load_timer.stop()
                return
            i = self.queue.pop(0)
            p = self.paths[i]
            try:
                self.bases[p] = thumb(p)
                r = QImageReader(p)
                sz = r.size()
                self.small[p] = sz.isValid() and (sz.width() < 1920 or sz.height() < 1080)
            except OSError:
                continue
            self.grid.item(i).setIcon(tile(self.bases[p], self.sel[p], self.small.get(p, False)))

    def paint(self, item):
        p = item.data(Qt.ItemDataRole.UserRole)
        if p in self.bases:
            item.setIcon(tile(self.bases[p], self.sel[p], self.small.get(p, False)))

    def toggle(self, item):
        p = item.data(Qt.ItemDataRole.UserRole)
        self.sel[p] = not self.sel[p]
        self.paint(item)
        self.refresh_count()

    def set_all(self, on):
        for i in range(self.grid.count()):
            it = self.grid.item(i)
            self.sel[it.data(Qt.ItemDataRole.UserRole)] = on
            self.paint(it)
        self.refresh_count()

    def invert(self):
        for i in range(self.grid.count()):
            it = self.grid.item(i)
            p = it.data(Qt.ItemDataRole.UserRole)
            self.sel[p] = not self.sel[p]
            self.paint(it)
        self.refresh_count()

    def add_pictures(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add pictures", HOME + "/Pictures", "Images (*.jpg *.jpeg *.png *.webp)")
        for f in files:
            if f in self.sel:
                self.sel[f] = True
                continue
            self.paths.append(f)
            self.sel[f] = True
            it = QListWidgetItem(os.path.basename(f).rsplit(".", 1)[0])
            it.setData(Qt.ItemDataRole.UserRole, f)
            it.setSizeHint(QSize(TW + 12, TH + 34))
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.grid.addItem(it)
            self.queue.append(self.grid.count() - 1)
            self.load_timer.start(5)
        self.refresh_count()

    def refresh_count(self):
        n = sum(self.sel.values())
        self.count.setText(f"{n} of {len(self.paths)} selected")
        self.next_btn.setEnabled(n > 0)
        self.warn.setText("" if n else "Pick at least one picture")

    # -------------------------------------------------------------- page 2
    def card(self, title, hint=None):
        f = QFrame()
        f.setObjectName("card")
        v = QVBoxLayout(f)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("section")
        v.addWidget(t)
        if hint:
            h = QLabel(hint)
            h.setObjectName("hint")
            h.setWordWrap(True)
            v.addWidget(h)
        return f, v

    def page_settings(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        t = QLabel("How should they change?")
        t.setObjectName("title")
        s = QLabel("Step 2 of 2")
        s.setObjectName("sub")
        v.addWidget(t)
        v.addWidget(s)
        cols = QHBoxLayout()
        cols.setSpacing(14)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(12)
        right.setSpacing(12)

        card, cv = self.card("Order")
        self.order_group = QButtonGroup(self)
        self.order_btns = {}
        for key, name, desc in ORDERS:
            rb = QRadioButton(name)
            self.order_group.addButton(rb)
            self.order_btns[key] = rb
            d = QLabel(desc)
            d.setObjectName("hint")
            d.setContentsMargins(26, 0, 0, 4)
            d.setWordWrap(True)
            cv.addWidget(rb)
            cv.addWidget(d)
            rb.toggled.connect(self.refresh_summary)
        self.order_btns.get(self.cfg["order"], self.order_btns["shuffle"]).setChecked(True)
        left.addWidget(card)

        card, cv = self.card("When to change")
        self.interval = QComboBox()
        for name, mins in INTERVALS:
            self.interval.addItem(name, mins)
        idx = self.interval.findData(self.cfg.get("interval", 30))
        self.interval.setCurrentIndex(idx if idx >= 0 else 3)
        self.interval.currentIndexChanged.connect(self.refresh_summary)
        self.on_login = QCheckBox("Also pick a new one every time I log in")
        self.on_login.setChecked(bool(self.cfg.get("on_login")))
        self.on_login.toggled.connect(self.refresh_summary)
        cv.addWidget(self.interval)
        cv.addWidget(self.on_login)
        hint = QLabel("You can always change it by hand with Super+Shift+W.")
        hint.setObjectName("hint")
        cv.addWidget(hint)
        left.addWidget(card)
        left.addStretch()

        card, cv = self.card("Parallax", "The wallpaper drifts a little against your mouse pointer, so the desktop feels like it has depth.")
        self.parallax = QCheckBox("Move the wallpaper with my mouse")
        self.parallax.setChecked(bool(self.cfg.get("parallax")))
        self.amount = QComboBox()
        for name, key in AMOUNTS:
            self.amount.addItem(name, key)
        self.amount.setCurrentIndex(max(0, self.amount.findData(self.cfg.get("parallax_amount", "medium"))))
        row = QHBoxLayout()
        row.addSpacing(26)
        lab = QLabel("How far")
        lab.setObjectName("hint")
        row.addWidget(lab)
        row.addWidget(self.amount)
        row.addStretch()
        cv.addWidget(self.parallax)
        cv.addLayout(row)
        self.parallax.toggled.connect(self.refresh_summary)
        self.amount.currentIndexChanged.connect(self.refresh_summary)
        right.addWidget(card)

        card, cv = self.card("Other")
        self.per_ws = QCheckBox("A different wallpaper on each workspace")
        self.per_ws.setChecked(bool(self.cfg.get("per_workspace")))
        pw = QLabel("Workspace 1 gets the first picture, workspace 2 the second, and so on.")
        pw.setObjectName("hint")
        pw.setWordWrap(True)
        pw.setContentsMargins(26, 0, 0, 4)
        self.lock = QCheckBox("Make the lock screen match the wallpaper")
        self.lock.setChecked(bool(self.cfg.get("lock_follows", True)))
        cv.addWidget(self.per_ws)
        cv.addWidget(pw)
        cv.addWidget(self.lock)
        self.per_ws.toggled.connect(self.refresh_summary)
        right.addWidget(card)

        card, cv = self.card("Summary")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        cv.addWidget(self.summary)
        right.addWidget(card)
        right.addStretch()

        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        v.addLayout(cols, 1)

        foot = QHBoxLayout()
        back = QPushButton("←  Back")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        now = QPushButton("Change now")
        now.clicked.connect(lambda: subprocess.Popen([HOME + "/.config/i3/scripts/wallpaper.sh", "next"]))
        self.status = QLabel("")
        self.status.setObjectName("status")
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(lambda: self.apply(False))
        done = QPushButton("Apply && close")
        done.setObjectName("primary")
        done.clicked.connect(lambda: self.apply(True))
        foot.addWidget(back)
        foot.addWidget(now)
        foot.addWidget(self.status)
        foot.addStretch()
        foot.addWidget(apply_btn)
        foot.addWidget(done)
        v.addLayout(foot)
        self.refresh_summary()
        return w

    def go_settings(self):
        self.stack.setCurrentIndex(1)
        self.refresh_summary()

    def current_order(self):
        return next((k for k, b in self.order_btns.items() if b.isChecked()), "shuffle")

    def refresh_summary(self, *_):
        if not hasattr(self, "summary"):
            return
        per = self.per_ws.isChecked()
        self.amount.setEnabled(self.parallax.isChecked())
        single = self.current_order() == "single"
        self.interval.setEnabled(not single)
        self.on_login.setEnabled(not single)
        n = sum(self.sel.values())
        order = dict((k, n_) for k, n_, _ in ORDERS)[self.current_order()]
        if single:
            when = "never changes"
        else:
            when = self.interval.currentText().lower() if self.interval.currentData() else "no automatic change"
            if self.on_login.isChecked():
                when += ", and at every login"
        fx = f"moves with the mouse ({self.amount.currentText().lower()})" if self.parallax.isChecked() else "no parallax"
        if per:
            fx += "  ·  a different picture on each workspace"
        self.summary.setText(f"{n} wallpaper{'s' if n != 1 else ''}  ·  {order.lower()}\n{when}\n{fx}"
                             f"{'  ·  lock screen follows' if self.lock.isChecked() else ''}")

    def apply(self, close):
        cfg = load_cfg()
        chosen = [p for p in self.paths if self.sel.get(p)]
        cfg.update({"list": chosen, "order": self.current_order(), "interval": int(self.interval.currentData() or 0),
                    "on_login": self.on_login.isChecked(), "parallax": self.parallax.isChecked(),
                    "parallax_amount": self.amount.currentData(), "per_workspace": self.per_ws.isChecked(),
                    "lock_follows": self.lock.isChecked()})
        os.makedirs(os.path.dirname(CFG), exist_ok=True)
        json.dump(cfg, open(CFG, "w"), indent=2)
        running = subprocess.run(["pgrep", "-f", "python3 .*[p]arallax.py"], capture_output=True).returncode == 0
        if running:
            subprocess.Popen([HOME + "/.config/i3/scripts/wallpaper.sh", "reload"])
        else:
            subprocess.Popen(["python3", HOME + "/.config/i3/scripts/parallax.py"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.status.setText("Applied ✓")
        QTimer.singleShot(2500, lambda: self.status.setText(""))
        if close:
            QTimer.singleShot(300, self.close)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.stack.currentIndex() == 0 and self.next_btn.isEnabled():
            self.go_settings()
        else:
            super().keyPressEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setDesktopFileName("wallpaperpicker")
    make_icons()
    app.setStyleSheet(STYLE.replace("ARROW", CACHE + "/arrow.png").replace("CHECK", CACHE + "/check.png"))
    w = Picker()
    w.resize(1180, 780)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
