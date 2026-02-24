# claude-code-idle-overlay

A small always-on-top overlay that shows how long Claude Code has been waiting for your input.

![overlay screenshot](screenshot.png)

## The Problem

When running multiple Claude Code sessions across different terminals, there's no way to tell which session finished and how long ago. The terminal tab title can't be changed due to ConPTY limitations.

## The Solution

A tiny semi-transparent overlay appears at the bottom-right corner of the terminal window that completed its response, showing elapsed idle time:

```
 ⏳ 2m 15s
```

- Appears on the correct terminal window (not just the focused one)
- Auto-closes when you send the next prompt
- Click to dismiss manually
- No dependencies beyond Python's built-in `tkinter`

## Requirements

- **Windows** (uses Win32 API for window positioning)
- **Python 3.8+** with tkinter (included in standard Python on Windows)
- **Claude Code** with hooks support

## Installation

1. Clone this repository into your Claude Code hooks directory:

```bash
cd ~/.claude/hooks
git clone https://github.com/johnnymny/claude-code-idle-overlay.git idle_overlay
```

2. Add the hooks to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python ~/.claude/hooks/idle_overlay/idle_overlay_stop_hook.py"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python ~/.claude/hooks/idle_overlay/idle_overlay_prompt_hook.py"
          }
        ]
      }
    ]
  }
}
```

> **Note:** If you already have hooks configured, add the new entries to your existing arrays.

## How It Works

```
UserPromptSubmit → idle_overlay_prompt_hook.py
                   ├── writes .idle_overlay_stop_{session_id}  (closes any existing overlay)
                   └── saves terminal window rect to .idle_overlay_rect_{session_id}

Stop → idle_overlay_stop_hook.py
       ├── reads saved window rect
       └── spawns idle_overlay.py at bottom-right of that terminal
```

The key insight: at prompt submission time, the user is definitely typing in the correct terminal, so `GetForegroundWindow()` captures the right window. This rect is saved and reused when the response completes (at which point the user may be looking at a different terminal).

## Configuration

Edit the constants at the top of `idle_overlay.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BG_COLOR` | `#1e1e2e` | Background color |
| `FG_COLOR` | `#cdd6f4` | Text color |
| `ALPHA` | `0.85` | Window opacity (0.0 - 1.0) |
| `FONT` | `("Segoe UI", 11)` | Font family and size |
| `COARSE_THRESHOLD` | `300` | Seconds before switching to minute-only display |
| `MARGIN` | `10` | Pixels from window edge |

## Limitations

- **Windows only** — uses `ctypes.windll` for Win32 window APIs and tkinter's `-toolwindow` attribute
- **Terminal multiplexers (tmux, screen):** The overlay positions relative to the terminal window, not individual panes. In tmux setups, the overlay will appear at the bottom-right of the entire terminal window
- **Agent Teams:** The overlay is suppressed during Agent Teams sessions to avoid noise from intermediate stops

## License

MIT
