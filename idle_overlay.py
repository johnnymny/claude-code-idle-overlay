"""Idle overlay: always-on-top timer showing how long Claude Code has been waiting.

Usage: idle_overlay.py <session_id> <start_time> [win_left win_top win_right win_bottom]
Spawned by idle_overlay_stop_hook.py on Stop event.
Stopped by: click on window, or .idle_overlay_stop_{session_id} sentinel file.

Pure Win32 implementation — no tkinter, no focus stealing.
"""
import ctypes
from ctypes import wintypes
import os
import time
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))

# Appearance
BG_RGB = (0x1e, 0x1e, 0x2e)
FG_COLORREF = 0xf4d6cd  # BGR for #cdd6f4
BG_COLORREF = 0x2e1e1e  # BGR for #1e1e2e
ALPHA_BYTE = int(0.85 * 255)
FONT_NAME = "Segoe UI"
FONT_SIZE = 14
WIDTH = 120
HEIGHT = 36
MARGIN = 10
POLL_MS = 200
COARSE_THRESHOLD = 300

# Win32 constants
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
SW_SHOWNOACTIVATE = 4
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_TIMER = 0x0113
WM_LBUTTONDOWN = 0x0201
WM_MOUSEACTIVATE = 0x0021
MA_NOACTIVATE = 3
DT_CENTER = 0x0001
DT_VCENTER = 0x0004
DT_SINGLELINE = 0x0020
TRANSPARENT = 1
TIMER_UPDATE = 1
TIMER_STOP = 2
IDC_ARROW = 32512

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, wintypes.HWND, wintypes.UINT,
    wintypes.WPARAM, wintypes.LPARAM,
)

HANDLE = ctypes.c_void_p  # generic handle for HCURSOR, HICON, HBRUSH etc.

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Set argtypes for Win32 functions to avoid 64-bit overflow errors
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_long
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), HANDLE]
user32.FillRect.restype = ctypes.c_int


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", HANDLE),
        ("hCursor", HANDLE),
        ("hbrBackground", HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", HANDLE),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", wintypes.BYTE * 32),
    ]


# Global state shared with wndproc
_start_time = 0.0
_stop_file = ""
_font = None
_brush = None


def _wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_MOUSEACTIVATE:
        return MA_NOACTIVATE

    if msg == WM_LBUTTONDOWN:
        user32.DestroyWindow(hwnd)
        return 0

    if msg == WM_PAINT:
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        rc = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rc))
        user32.FillRect(hdc, ctypes.byref(rc), _brush)

        elapsed = int(time.time() - _start_time)
        m, s = divmod(elapsed, 60)
        if elapsed >= COARSE_THRESHOLD:
            text = f"\u23f3 {m}m"
        elif m > 0:
            text = f"\u23f3 {m}m {s:02d}s"
        else:
            text = f"\u23f3 {s}s"

        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, FG_COLORREF)
        old = gdi32.SelectObject(hdc, _font)
        user32.DrawTextW(hdc, text, -1, ctypes.byref(rc),
                         DT_CENTER | DT_VCENTER | DT_SINGLELINE)
        gdi32.SelectObject(hdc, old)
        user32.EndPaint(hwnd, ctypes.byref(ps))
        return 0

    if msg == WM_TIMER:
        if wparam == TIMER_UPDATE:
            user32.InvalidateRect(hwnd, None, True)
        elif wparam == TIMER_STOP:
            if os.path.exists(_stop_file):
                try:
                    os.remove(_stop_file)
                except OSError:
                    pass
                user32.DestroyWindow(hwnd)
        return 0

    if msg == WM_DESTROY:
        user32.KillTimer(hwnd, TIMER_UPDATE)
        user32.KillTimer(hwnd, TIMER_STOP)
        if _font:
            gdi32.DeleteObject(_font)
        if _brush:
            gdi32.DeleteObject(_brush)
        user32.PostQuitMessage(0)
        return 0

    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


# prevent GC of the callback
_wnd_proc_cb = WNDPROC(_wnd_proc)


def main():
    global _start_time, _stop_file, _font, _brush

    if len(sys.argv) < 2:
        sys.exit(1)

    session_id = sys.argv[1]
    _stop_file = os.path.join(HOOKS_DIR, f".idle_overlay_stop_{session_id}")

    if os.path.exists(_stop_file):
        try:
            os.remove(_stop_file)
        except OSError:
            pass

    try:
        _start_time = float(sys.argv[2])
    except (IndexError, ValueError):
        _start_time = time.time()

    win_rect = None
    if len(sys.argv) >= 7:
        try:
            win_rect = (int(sys.argv[3]), int(sys.argv[4]),
                        int(sys.argv[5]), int(sys.argv[6]))
        except ValueError:
            pass

    if win_rect:
        x = win_rect[2] - WIDTH - MARGIN
        y = win_rect[3] - HEIGHT - MARGIN
    else:
        x = user32.GetSystemMetrics(0) - WIDTH - 20   # SM_CXSCREEN
        y = user32.GetSystemMetrics(1) - HEIGHT - 60   # SM_CYSCREEN

    hinstance = kernel32.GetModuleHandleW(None)
    class_name = f"IdleOverlay_{session_id}"

    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = CS_HREDRAW | CS_VREDRAW
    wc.lpfnWndProc = _wnd_proc_cb
    wc.hInstance = hinstance
    wc.hCursor = user32.LoadCursorW(None, IDC_ARROW)
    wc.lpszClassName = class_name
    user32.RegisterClassExW(ctypes.byref(wc))

    hwnd = user32.CreateWindowExW(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED,
        class_name, None,
        WS_POPUP,
        x, y, WIDTH, HEIGHT,
        None, None, hinstance, None,
    )
    if not hwnd:
        sys.exit(1)

    user32.SetLayeredWindowAttributes(hwnd, 0, ALPHA_BYTE, LWA_ALPHA)

    _font = gdi32.CreateFontW(
        -FONT_SIZE, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, FONT_NAME,
    )
    _brush = gdi32.CreateSolidBrush(BG_COLORREF)

    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)

    # Timer: 1s for display update, POLL_MS for stop-file check
    user32.SetTimer(hwnd, TIMER_UPDATE, 1000, None)
    user32.SetTimer(hwnd, TIMER_STOP, POLL_MS, None)

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    main()
