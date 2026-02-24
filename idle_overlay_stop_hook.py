"""Stop hook: launch idle overlay on every response completion.

Reads terminal window rect saved by idle_overlay_prompt_hook.py at prompt time.
"""
import sys
import json
import os
import glob
import subprocess

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
TEAMS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "teams")
OVERLAY_SCRIPT = os.path.join(HOOKS_DIR, "idle_overlay.py")

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

session_id = payload.get("session_id", "")
if not session_id:
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

subprocess.Popen(
    [sys.executable, OVERLAY_SCRIPT, session_id] + win_args,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
