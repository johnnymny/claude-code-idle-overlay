"""Stop hook: launch idle overlay when Claude Code becomes truly idle.

Reads terminal window rect saved by idle_overlay_prompt_hook.py at prompt time.
Waits LAUNCH_DELAY seconds, then checks transcript growth to distinguish
real idle from interim stops. Only launches overlay if transcript stopped growing.
"""
import sys
import json
import os
import glob
import subprocess
import time
import ctypes
from ctypes import wintypes

LAUNCH_DELAY = 3  # seconds to wait before launching overlay

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
TEAMS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "teams")
OVERLAY_SCRIPT = os.path.join(HOOKS_DIR, "idle_overlay.py")

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

session_id = payload.get("session_id", "")
transcript_path = payload.get("transcript_path", "")
if not session_id:
    sys.exit(0)

# Filter: non-interactive sessions (claude -p, subagents, Opus escalations)
# Interactive sessions use bypassPermissions; non-interactive use default.
permission_mode = payload.get("permission_mode", "")
if permission_mode != "bypassPermissions":
    sys.exit(0)

# Filter: no active team owned by this session (avoid overlay during Agent Teams)
if os.path.isdir(TEAMS_DIR):
    for config_path in glob.glob(os.path.join(TEAMS_DIR, "*/config.json")):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                team_config = json.load(f)
            if team_config.get("leadSessionId") == session_id:
                sys.exit(0)
        except Exception:
            continue

# Read terminal window rect saved at prompt submission time
win_args = []
rect_file = os.path.join(HOOKS_DIR, f".idle_overlay_rect_{session_id}")
try:
    with open(rect_file, "r") as f:
        win_args = f.read().strip().split(",")
except Exception:
    pass

start_time = time.time()
stop_file = os.path.join(HOOKS_DIR, f".idle_overlay_stop_{session_id}")

# Clear stop file left by prompt hook, then wait.
# Only a NEW prompt submission during the delay should prevent launch.
try:
    os.remove(stop_file)
except OSError:
    pass

# Snapshot transcript size before delay
try:
    initial_size = os.path.getsize(transcript_path) if transcript_path else 0
except OSError:
    initial_size = 0

time.sleep(LAUNCH_DELAY)

if os.path.exists(stop_file):
    sys.exit(0)

# Transcript grew during delay → Claude is still working (interim stop), skip
if transcript_path:
    try:
        if os.path.getsize(transcript_path) > initial_size:
            sys.exit(0)
    except OSError:
        pass

# Check for existing overlay via EnumWindows (FindWindowW unreliable — always returns 0)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_target_class = f"IdleOverlay_{session_id}"
_cls_buf = ctypes.create_unicode_buffer(256)
_existing_hwnd = []

def _enum_cb(hwnd, _):
    ctypes.windll.user32.GetClassNameW(hwnd, _cls_buf, 256)
    if _cls_buf.value == _target_class:
        _existing_hwnd.append(hwnd)
    return True

ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

if _existing_hwnd:
    sys.exit(0)

subprocess.Popen(
    [sys.executable, OVERLAY_SCRIPT, session_id, str(start_time)] + win_args,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
