"""Idle overlay: always-on-top timer showing how long Claude Code has been waiting.

Usage: idle_overlay.py <session_id> [win_left win_top win_right win_bottom]
Spawned by idle_overlay_stop_hook.py on Stop event.
Stopped by: click on window, or .idle_overlay_stop_{session_id} sentinel file.
"""
import tkinter as tk
import os
import time
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
POLL_MS = 200
BG_COLOR = "#1e1e2e"
FG_COLOR = "#cdd6f4"
ALPHA = 0.85
FONT = ("Segoe UI", 11)
WIDTH = 120
HEIGHT = 36
MARGIN = 10
# After this many seconds, switch from "Xm Ys" to "Xm" (updated every 60s)
COARSE_THRESHOLD = 300


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    session_id = sys.argv[1]
    stop_file = os.path.join(HOOKS_DIR, f".idle_overlay_stop_{session_id}")

    # Clean up stale stop file from previous run
    if os.path.exists(stop_file):
        try:
            os.remove(stop_file)
        except OSError:
            pass

    # Parse terminal window rect if provided
    win_rect = None
    if len(sys.argv) >= 6:
        try:
            win_rect = (int(sys.argv[2]), int(sys.argv[3]),
                        int(sys.argv[4]), int(sys.argv[5]))
        except ValueError:
            pass

    start_time = time.time()

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", ALPHA)
    root.attributes("-toolwindow", True)
    root.configure(bg=BG_COLOR)

    if win_rect:
        # Position at bottom-right of terminal window
        win_left, win_top, win_right, win_bottom = win_rect
        x = win_right - WIDTH - MARGIN
        y = win_bottom - HEIGHT - MARGIN
    else:
        # Fallback: bottom-right of screen
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = screen_w - WIDTH - 20
        y = screen_h - HEIGHT - 60

    root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    label = tk.Label(
        root,
        text="",
        font=FONT,
        fg=FG_COLOR,
        bg=BG_COLOR,
        anchor="center",
    )
    label.pack(expand=True, fill="both")

    def update_time():
        elapsed = int(time.time() - start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        if elapsed >= COARSE_THRESHOLD:
            label.config(text=f"\u23f3 {minutes}m")
            root.after(60000, update_time)
        elif minutes > 0:
            label.config(text=f"\u23f3 {minutes}m {seconds:02d}s")
            root.after(1000, update_time)
        else:
            label.config(text=f"\u23f3 {seconds}s")
            root.after(1000, update_time)

    def check_stop():
        if os.path.exists(stop_file):
            try:
                os.remove(stop_file)
            except OSError:
                pass
            root.destroy()
            return
        root.after(POLL_MS, check_stop)

    def on_click(event):
        root.destroy()

    root.bind("<Button-1>", on_click)
    label.bind("<Button-1>", on_click)

    update_time()
    check_stop()
    root.mainloop()


if __name__ == "__main__":
    main()
