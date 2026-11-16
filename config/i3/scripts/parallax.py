#!/usr/bin/env python3
"""Wallpaper daemon for Hyprland: draws the wallpaper itself (GTK3 + layer-shell, on top of hyprpaper) so it can
  * move slightly against your mouse pointer ("parallax"), smoothed so it glides,
  * crossfade when the wallpaper changes,
  * rotate on a timer / in a chosen order, and optionally show a different picture per workspace.
hyprpaper stays underneath as a static fallback. Settings live in ~/.config/hypr/wallpaper.json (written by the picker
wallpaper-picker.py, but plain JSON):
  list             wallpapers to use (paths)
  order            shuffle | sequential | random | single
  interval         minutes between automatic changes (0 = never)
  on_login         pick a new wallpaper each time the session starts
  parallax         move the wallpaper with the mouse
  parallax_amount  subtle | medium | strong
  per_workspace    a different wallpaper on each workspace
  lock_follows     regenerate the lock-screen background when the wallpaper changes
Signals: USR1 = reload the settings, USR2 = run the command in ~/.cache/parallax/cmd (next | prev | random | <path>)."""
import glob, json, math, os, random, signal, socket, subprocess, sys, time

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
except (ValueError, ImportError):
    GtkLayerShell = None
import cairo
try:
    gi.require_version("GLibUnix", "2.0")
    from gi.repository import GLibUnix
    unix_signal_add = GLibUnix.signal_add
except (ValueError, ImportError):
    unix_signal_add = GLib.unix_signal_add

HOME = os.path.expanduser("~")
CACHE = HOME + "/.cache/parallax"
CFG = HOME + "/.config/hypr/wallpaper.json"
ST = CACHE + "/state.json"
CMD = CACHE + "/cmd"
RT = os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())
SIG = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
AMOUNTS = {"subtle": 24, "medium": 48, "strong": 90}      # how far (px) the picture may shift each way
TAU = 0.12                                                # smoothing time constant (s)
FADE = 0.6                                                # crossfade length (s)
FRAME_MS = 22                                             # ~45 fps while something moves
DEFAULTS = {"list": [], "order": "shuffle", "interval": 30, "on_login": False, "parallax": True,
            "parallax_amount": "medium", "per_workspace": False, "lock_follows": True}

S = {"cfg": dict(DEFAULTS), "st": {"current": None, "queue": [], "history": []}, "ws": 1, "next_change": 0.0}


def sh(*a, timeout=30):
    return subprocess.run(list(a), capture_output=True, text=True, timeout=timeout)


# ------------------------------------------------------------------ settings / state
def default_list():
    lst = []
    try:
        lst = [l.strip() for l in open(HOME + "/.config/hypr/wallpaper-list") if l.strip()]
    except OSError:
        pass
    return [p for p in lst if os.path.exists(p)] or sorted(glob.glob(HOME + "/Pictures/wall.*.jpg"))[:12]


def load_cfg():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.load(open(CFG)))
    except (OSError, ValueError):
        cfg["list"] = default_list()
        os.makedirs(os.path.dirname(CFG), exist_ok=True)
        json.dump(cfg, open(CFG, "w"), indent=2)
    cfg["list"] = [p for p in cfg["list"] if os.path.exists(p)]
    if cfg["order"] not in ("shuffle", "sequential", "random", "single"):
        cfg["order"] = "shuffle"
    if cfg["parallax_amount"] not in AMOUNTS:
        cfg["parallax_amount"] = "medium"
    S["cfg"] = cfg


def load_state():
    try:
        S["st"].update(json.load(open(ST)))
    except (OSError, ValueError):
        pass


def save_state():
    os.makedirs(CACHE, exist_ok=True)
    json.dump(S["st"], open(ST, "w"))


def schedule():
    iv = S["cfg"]["interval"]
    S["next_change"] = time.time() + iv * 60 if iv and iv > 0 else 0.0


def choose(direction="next"):
    lst, st, cfg = S["cfg"]["list"], S["st"], S["cfg"]
    cur = st.get("current")
    if not lst:
        return cur
    order = cfg["order"]
    if order == "single":
        return cur if cur in lst else lst[0]
    if order == "sequential":
        if cur not in lst:
            return lst[0]
        return lst[(lst.index(cur) + (1 if direction == "next" else -1)) % len(lst)]
    if order == "random":
        return random.choice([p for p in lst if p != cur] or lst)
    if direction == "prev":                               # shuffle: step back through what was shown
        hist = st.get("history", [])
        while hist:
            p = hist.pop()
            if p != cur and p in lst:
                return p
        return cur
    qu = [p for p in st.get("queue", []) if p in lst and p != cur]
    if not qu:                                            # new round: every picture once, never the same twice in a row
        qu = lst[:]
        random.shuffle(qu)
        if len(qu) > 1 and qu[0] == cur:
            qu.append(qu.pop(0))
    nxt = qu.pop(0)
    st["queue"] = qu
    return nxt


def ws_path(ws):
    lst = S["cfg"]["list"]
    return lst[(ws - 1) % len(lst)] if lst else S["st"].get("current")


def lock_background(path):
    out = HOME + "/.cache/lock-blur.png"
    subprocess.Popen(["magick", path + "[0]", "-resize", "1920x1080^", "-gravity", "center", "-extent", "1920x1080", "-blur", "0x12",
                      "-colorspace", "Gray", "-fill", "#0a0a0a", "-colorize", "45%", "-colorspace", "sRGB", out],
                     stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ hyprland
def hypr_cmd(cmd):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(f"{RT}/hypr/{SIG}/.socket.sock")
        s.sendall(cmd.encode())
        data = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            data += c
        return data.decode()
    except OSError:
        return ""
    finally:
        s.close()


def cursor_pos():
    try:
        d = json.loads(hypr_cmd("j/cursorpos"))
        return float(d["x"]), float(d["y"])
    except Exception:
        return None


def set_underlay(path):
    """keep hyprpaper's static copy in sync, so a crash of this program leaves the right picture behind"""
    subprocess.Popen(["hyprctl", "hyprpaper", "wallpaper", f",{path},cover"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ drawing
class Layer:
    """one wallpaper window, covering one monitor"""

    def __init__(self, mon):
        g = mon.get_geometry()
        self.x, self.y, self.w, self.h = g.x, g.y, g.width, g.height
        self.cur = self.prev = None
        self.path = None
        self.fade = 1.0
        self.ox = self.oy = 0.0
        self.m = 0
        self.win = Gtk.Window()
        self.win.set_decorated(False)
        self.win.set_app_paintable(True)
        GtkLayerShell.init_for_window(self.win)
        GtkLayerShell.set_monitor(self.win, mon)
        GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.BACKGROUND)
        for e in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.win, e, True)
        GtkLayerShell.set_exclusive_zone(self.win, -1)
        GtkLayerShell.set_keyboard_mode(self.win, GtkLayerShell.KeyboardMode.NONE)
        GtkLayerShell.set_namespace(self.win, "wallpaper-parallax")
        self.area = Gtk.DrawingArea()
        self.area.connect("draw", self.on_draw)
        self.win.add(self.area)
        self.win.connect("realize", lambda w: w.get_window().input_shape_combine_region(cairo.Region(), 0, 0))
        self.win.show_all()

    def load(self, path):
        tw, th = self.w + 2 * self.m, self.h + 2 * self.m
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
        s = max(tw / pb.get_width(), th / pb.get_height())
        nw, nh = max(tw, math.ceil(pb.get_width() * s)), max(th, math.ceil(pb.get_height() * s))
        pb = pb.scale_simple(nw, nh, GdkPixbuf.InterpType.HYPER)
        pb = pb.new_subpixbuf((nw - tw) // 2, (nh - th) // 2, tw, th)
        return Gdk.cairo_surface_create_from_pixbuf(pb, 1, None)

    def set_image(self, path, margin, fade=True):
        if path == self.path and margin == self.m:
            return
        try:
            self.m = margin
            surf = self.load(path)
        except Exception as e:
            print("cannot load", path, e, file=sys.stderr)
            return
        same = (path == self.path)
        self.prev = self.cur if (fade and self.cur is not None and not same) else None
        self.cur, self.path = surf, path
        self.fade = 0.0 if self.prev is not None else 1.0
        self.area.queue_draw()

    def on_draw(self, widget, cr):
        if self.cur is None:
            cr.set_source_rgb(0.04, 0.04, 0.04)
            cr.paint()
            return False
        ox, oy = round(self.ox) - self.m, round(self.oy) - self.m
        cr.set_operator(cairo.OPERATOR_SOURCE)                # plain copy: the picture always covers the whole window
        if self.prev is not None and self.fade < 1.0:
            cr.set_source_surface(self.prev, ox, oy)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            cr.set_source_surface(self.cur, ox, oy)
            cr.paint_with_alpha(min(1.0, self.fade))
        else:
            cr.set_source_surface(self.cur, ox, oy)
            cr.paint()
        return False


class Daemon:
    def __init__(self):
        disp = Gdk.Display.get_default()
        self.layers = [Layer(disp.get_monitor(i)) for i in range(disp.get_n_monitors())]
        self.last = time.monotonic()
        self.active_until = 0.0
        self.src = None
        self.src_ms = 0
        self.lastpos = None
        self.ev_buf = b""

    # ---- showing
    def margin(self):
        return AMOUNTS[S["cfg"]["parallax_amount"]] if S["cfg"]["parallax"] else 0

    def show_current(self, fade=True):
        cfg = S["cfg"]
        cur = S["st"].get("current")
        path = ws_path(S["ws"]) if cfg["per_workspace"] and cfg["list"] else cur
        if not path or not os.path.exists(path):
            return
        for L in self.layers:
            L.set_image(path, self.margin(), fade)
            if not cfg["parallax"]:
                L.ox = L.oy = 0.0
        self.kick()

    def change_to(self, path):
        st = S["st"]
        old = st.get("current")
        if old and old != path:
            st["history"] = (st.get("history", []) + [old])[-30:]
        st["current"] = path
        save_state()
        self.show_current()
        set_underlay(path)
        if S["cfg"]["lock_follows"]:
            lock_background(path)
        schedule()

    # ---- the animation tick: fast while something moves, slow when idle
    def kick(self):
        self.active_until = time.monotonic() + 1.0
        self.schedule_tick(FRAME_MS)

    def schedule_tick(self, ms):
        """at most one pending tick; a faster request replaces a slower pending one"""
        if self.src is not None:
            if ms >= self.src_ms:
                return
            GLib.source_remove(self.src)
        self.src_ms = ms
        self.src = GLib.timeout_add(ms, self.run_tick)

    def run_tick(self):
        self.src = None
        self.tick()
        self.schedule_tick(FRAME_MS if time.monotonic() < self.active_until else 120)
        return False

    def tick(self):
        now = time.monotonic()
        dt, self.last = min(now - self.last, 0.1), now
        a = 1 - math.exp(-dt / TAU)
        pos = cursor_pos() if S["cfg"]["parallax"] else None
        moved = pos is not None and pos != self.lastpos
        if pos is not None:
            self.lastpos = pos
        busy = moved
        for L in self.layers:
            redraw = False
            if pos is not None and L.m:
                nx = min(1.0, max(0.0, (pos[0] - L.x) / L.w))
                ny = min(1.0, max(0.0, (pos[1] - L.y) / L.h))
                tx, ty = -(nx - 0.5) * 2 * L.m, -(ny - 0.5) * 2 * L.m
                if abs(tx - L.ox) > 0.15 or abs(ty - L.oy) > 0.15:
                    L.ox += (tx - L.ox) * a
                    L.oy += (ty - L.oy) * a
                    redraw = True
            if L.fade < 1.0:
                L.fade = min(1.0, L.fade + dt / FADE)
                if L.fade >= 1.0:
                    L.prev = None
                redraw = True
            if redraw:
                L.area.queue_draw()
                busy = True
        if busy:
            self.active_until = now + 1.0
        if S["next_change"] and time.time() >= S["next_change"]:     # rotation timer
            self.change_to(choose("next"))

    # ---- external input
    def on_reload(self):
        load_cfg()
        cfg = S["cfg"]
        if cfg["order"] == "single" and cfg["list"]:
            self.change_to(cfg["list"][0])
        elif cfg["list"] and S["st"].get("current") not in cfg["list"]:
            S["st"]["current"] = None
            self.change_to(choose("next"))
        else:
            self.show_current(fade=False)
            schedule()
            if cfg["lock_follows"] and S["st"].get("current"):
                lock_background(S["st"]["current"])
        for L in self.layers:
            if not cfg["parallax"]:
                L.ox = L.oy = 0.0
                L.area.queue_draw()
        self.kick()
        return True

    def on_cmd(self):
        try:
            cmd = open(CMD).read().strip()
        except OSError:
            return True
        if cmd in ("next", "prev"):
            self.change_to(choose(cmd))
        elif cmd == "random":
            lst = [p for p in S["cfg"]["list"] if p != S["st"].get("current")]
            if lst:
                self.change_to(random.choice(lst))
        elif os.path.exists(cmd):
            self.change_to(cmd)
        return True

    def connect_events(self):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(f"{RT}/hypr/{SIG}/.socket2.sock")
            s.setblocking(False)
            self.ev_sock = s
            GLib.io_add_watch(s.fileno(), GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR, self.on_event)
        except OSError:
            GLib.timeout_add_seconds(2, lambda: self.connect_events() and False)

    def on_event(self, fd, cond):
        try:
            data = self.ev_sock.recv(4096)
        except BlockingIOError:
            return True
        except OSError:
            data = b""
        if not data:
            GLib.timeout_add_seconds(2, lambda: self.connect_events() and False)
            return False
        self.ev_buf += data
        while b"\n" in self.ev_buf:
            line, self.ev_buf = self.ev_buf.split(b"\n", 1)
            if line.startswith(b"workspacev2>>") and S["cfg"]["per_workspace"]:
                try:
                    S["ws"] = int(line.split(b">>")[1].split(b",")[0])
                except ValueError:
                    continue
                self.show_current()
        return True


def main():
    os.makedirs(CACHE, exist_ok=True)
    if GtkLayerShell is None or not GtkLayerShell.is_supported():
        sys.exit("layer-shell is not available (needs gtk-layer-shell and a compositor with wlr-layer-shell)")
    load_cfg()
    load_state()
    cur = S["st"].get("current")
    if S["cfg"]["on_login"] and S["cfg"]["list"]:
        cur = choose("next")
    if not cur or not os.path.exists(cur):
        cur = choose("next") or (S["cfg"]["list"][0] if S["cfg"]["list"] else None)
    S["st"]["current"] = cur
    save_state()
    try:
        S["ws"] = int(json.loads(hypr_cmd("j/activeworkspace"))["id"])
    except Exception:
        S["ws"] = 1
    d = Daemon()
    d.show_current(fade=False)
    if cur:
        set_underlay(cur)
    schedule()
    d.connect_events()
    unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR1, d.on_reload)
    unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR2, d.on_cmd)
    d.kick()
    Gtk.main()


if __name__ == "__main__":
    main()
