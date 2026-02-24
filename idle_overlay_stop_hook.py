"""Stop hook: launch idle overlay on every response completion.

Reads terminal window rect saved by idle_overlay_prompt_hook.py at prompt time.
Waits LAUNCH_DELAY seconds before launching to skip intermediate Stop events
(e.g., between tool calls). If the user sends a new prompt during the delay,
the stop sentinel file will exist and we skip launching.
"""
import sys
import json
import os
import glob
import subprocess
import time

LAUNCH_DELAY = 3  # seconds to wait before launching overlay

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

start_time = time.time()
stop_file = os.path.join(HOOKS_DIR, f".idle_overlay_stop_{session_id}")
pid_file = os.path.join(HOOKS_DIR, f".idle_overlay_pid_{session_id}")

# Skip if overlay already running for this session
try:
    with open(pid_file, "r") as f:
        old_pid = int(f.read().strip())
    os.kill(old_pid, 0)  # check if process exists (signal 0 = no-op)
    sys.exit(0)  # still alive → already idle, skip
except Exception:
    pass

# Clear stop file left by prompt hook, then wait.
# Only a NEW prompt submission during the delay should prevent launch.
try:
    os.remove(stop_file)
except OSError:
    pass
time.sleep(LAUNCH_DELAY)

if os.path.exists(stop_file):
    sys.exit(0)

proc = subprocess.Popen(
    [sys.executable, OVERLAY_SCRIPT, session_id, str(start_time)] + win_args,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Save PID so next invocation can kill this overlay
with open(pid_file, "w") as f:
    f.write(str(proc.pid))
