"""UserPromptSubmit hook: close existing overlay and save terminal window position.

On prompt submission:
1. Write a stop sentinel file to close any running overlay for this session
2. Capture the foreground window rect (the terminal the user is typing in)
"""
import sys
import json
import os
import ctypes
from ctypes import wintypes

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

session_id = payload.get("session_id", "")
if not session_id:
    sys.exit(0)

# Signal idle overlay for this session to close
stop_file = os.path.join(HOOKS_DIR, f".idle_overlay_stop_{session_id}")
with open(stop_file, "w") as f:
    f.write("stop")

# Save foreground window rect (user is typing in the correct terminal right now)
try:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    rect_file = os.path.join(HOOKS_DIR, f".idle_overlay_rect_{session_id}")
    with open(rect_file, "w") as f:
        f.write(f"{rect.left},{rect.top},{rect.right},{rect.bottom}")
except Exception:
    pass
