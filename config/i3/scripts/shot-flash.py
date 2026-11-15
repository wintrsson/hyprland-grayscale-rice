#!/usr/bin/env python3
"""A quick camera-shutter flash: a full-screen white-ish overlay that fades out in ~0.3 s (override-redirect, so it never steals focus)."""
import tkinter as tk
r = tk.Tk()
r.overrideredirect(True)
r.geometry(f"{r.winfo_screenwidth()}x{r.winfo_screenheight()}+0+0")
r.configure(bg="white")
r.attributes("-topmost", True)
steps = 10
def fade(i=0):
    if i >= steps:
        r.destroy(); return
    r.attributes("-alpha", 0.55 * (1 - i / steps))
    r.after(25, fade, i + 1)
r.attributes("-alpha", 0.55)
r.after(40, fade)
r.mainloop()
