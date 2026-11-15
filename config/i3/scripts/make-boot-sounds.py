#!/usr/bin/env python3
"""Renders the one sound that plays as a file: the final 'system ready' sound (so it can finish playing after the
splash window closes). All other boot sounds are synthesized live by bootsynth.py. Re-run after editing bootsynth.py."""
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootsynth  # noqa: E402

out = os.path.expanduser("~/.config/i3/sounds")
os.makedirs(out, exist_ok=True)
x = bootsynth.build_ready()
with wave.open(os.path.join(out, "ready.wav"), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(bootsynth.SR)
    w.writeframes((x * 32767).astype("<i2").tobytes())
print(f"ready.wav  {len(x) / bootsynth.SR:.2f}s  peak {np.abs(x).max():.2f}")
