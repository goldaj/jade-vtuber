#!/usr/bin/env python3
"""Minimal, deterministic Windows input driver for the existing Cubism window.

This is used only when the desktop Computer Use bridge cannot capture Cubism's
Java window.  It never launches Cubism and refuses to act unless exactly one
visible Cubism Editor window exists.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab


user32 = ctypes.windll.user32
try:
    # Use the same physical pixel coordinate space as full-screen screenshots.
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    user32.SetProcessDPIAware()
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


VK = {
    "W": 0x57,
    "CTRL": 0x11,
    "SHIFT": 0x10,
    "ALT": 0x12,
    "ENTER": 0x0D,
    "ESC": 0x1B,
    "TAB": 0x09,
    "SPACE": 0x20,
    "O": 0x4F,
    "S": 0x53,
    "N": 0x4E,
    "A": 0x41,
    "F": 0x46,
    "V": 0x56,
    "Z": 0x5A,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "F4": 0x73,
}


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def visible_windows() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            title = window_title(hwnd)
            if title:
                found.append((int(hwnd), title))
        return True

    user32.EnumWindows(callback, 0)
    return found


def cubism_window(title_contains: str | None = None) -> int:
    candidates = [
        (hwnd, title)
        for hwnd, title in visible_windows()
        if title.startswith("Live2D Cubism Editor ")
        and (title_contains is None or title_contains in title)
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one Cubism window, found: {candidates}")
    return candidates[0][0]


def require_unlocked_desktop() -> None:
    """Refuse input/capture when Windows has switched to its secure desktop."""
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                               ctypes.c_void_p, wintypes.DWORD,
                                               ctypes.POINTER(wintypes.DWORD)]
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    desktop = user32.OpenInputDesktop(0, False, 1)
    if not desktop:
        raise RuntimeError("input desktop unavailable; stop until the user unlocks Windows")
    try:
        name = ctypes.create_unicode_buffer(256)
        needed = wintypes.DWORD()
        if not user32.GetUserObjectInformationW(desktop, 2, name, ctypes.sizeof(name), ctypes.byref(needed)):
            raise RuntimeError("cannot establish unlocked desktop; refusing UI actions")
        if name.value != "Default":
            raise RuntimeError("secure/locked desktop active; refusing UI actions")
    finally:
        user32.CloseDesktop(desktop)


def target_window(use_foreground: bool, title_contains: str | None = None) -> int:
    require_unlocked_desktop()
    hwnd = (
        int(user32.GetForegroundWindow())
        if use_foreground
        else cubism_window(title_contains)
    )
    if not hwnd:
        raise RuntimeError("no target window")
    if use_foreground and title_contains and title_contains not in window_title(hwnd):
        raise RuntimeError(f"foreground changed; expected {title_contains!r}, refusing input")
    if not use_foreground:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.35)
    return hwnd


def key_event(vk: int, up: bool = False) -> None:
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, 0)


def mouse_input(flags: int, data: int = 0) -> None:
    event = INPUT(
        type=0,
        mi=MOUSEINPUT(0, 0, data, flags, 0, None),
    )
    if user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
        raise RuntimeError("SendInput mouse event failed")


def press_chord(tokens: list[str]) -> None:
    keys = [VK[token.upper()] for token in tokens]
    for key in keys:
        key_event(key)
    for key in reversed(keys):
        key_event(key, True)


def type_unicode(value: str) -> None:
    for char in value:
        code = ord(char)
        down = INPUT(type=1, ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, None))
        up = INPUT(
            type=1,
            ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None),
        )
        if user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT)) != 1:
            raise RuntimeError("SendInput unicode key-down failed")
        if user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT)) != 1:
            raise RuntimeError("SendInput unicode key-up failed")


def type_virtual_text(value: str) -> None:
    """Type through layout-aware virtual keys for Java/Swing text widgets."""
    for char in value:
        encoded = user32.VkKeyScanW(ord(char))
        if encoded == -1:
            raise RuntimeError(f"no virtual-key mapping for {char!r}")
        key = encoded & 0xFF
        modifier_bits = (encoded >> 8) & 0xFF
        modifiers = []
        if modifier_bits & 1:
            modifiers.append(VK["SHIFT"])
        if modifier_bits & 2:
            modifiers.append(VK["CTRL"])
        if modifier_bits & 4:
            modifiers.append(VK["ALT"])
        for modifier in modifiers:
            key_event(modifier)
        key_event(key)
        key_event(key, True)
        for modifier in reversed(modifiers):
            key_event(modifier, True)


def paste_text(value: str, owner: int) -> None:
    cf_unicode_text = 13
    gmem_moveable = 0x0002
    data = (value + "\0").encode("utf-16-le")
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p
    user32.SetClipboardData.restype = ctypes.c_void_p
    handle = kernel32.GlobalAlloc(gmem_moveable, len(data))
    if not handle:
        raise RuntimeError("GlobalAlloc failed")
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        raise RuntimeError("GlobalLock failed")
    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.OpenClipboard(owner):
        raise RuntimeError("OpenClipboard failed")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(cf_unicode_text, handle):
            raise RuntimeError("SetClipboardData failed")
        handle = None  # ownership transferred to Windows
    finally:
        user32.CloseClipboard()
    press_chord(["CTRL", "V"])


def rect(hwnd: int) -> tuple[int, int, int, int]:
    value = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(value)):
        raise RuntimeError("GetWindowRect failed")
    return value.left, value.top, value.right, value.bottom


def capture(hwnd: int, output: Path, full_screen: bool = False) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if full_screen:
        ImageGrab.grab(all_screens=True).save(output)
    else:
        ImageGrab.grab(bbox=rect(hwnd), all_screens=True).save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "state",
            "hotkey",
            "text",
            "paste",
            "click",
            "click-paste",
            "click-replace",
            "click-type",
            "scroll",
        ),
    )
    parser.add_argument("--keys", nargs="+")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--text")
    parser.add_argument("--x", type=int)
    parser.add_argument("--y", type=int)
    parser.add_argument("--modifiers", nargs="+", choices=("CTRL", "SHIFT", "ALT"))
    parser.add_argument("--delta", type=int)
    parser.add_argument("--foreground", action="store_true")
    parser.add_argument("--title-contains")
    parser.add_argument("--full-screen", action="store_true")
    parser.add_argument("--wait", type=float, default=0.8)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    hwnd = target_window(args.foreground, args.title_contains)
    if args.action != "state" and int(user32.GetForegroundWindow()) != hwnd:
        raise RuntimeError("target did not acquire foreground; refusing input, activate through Computer Use first")
    if args.action == "hotkey":
        if not args.keys:
            raise RuntimeError("--keys required")
        if args.repeat < 1 or args.repeat > 100:
            raise RuntimeError("--repeat must be between 1 and 100")
        for index in range(args.repeat):
            press_chord(args.keys)
            if index + 1 < args.repeat:
                time.sleep(0.08)
    elif args.action == "text":
        if args.text is None:
            raise RuntimeError("--text required")
        type_unicode(args.text)
    elif args.action == "paste":
        if args.text is None:
            raise RuntimeError("--text required")
        paste_text(args.text, hwnd)
    elif args.action in ("click", "click-paste", "click-replace", "click-type"):
        if args.x is None or args.y is None:
            raise RuntimeError("--x/--y required")
        left, top, _right, _bottom = rect(hwnd)
        user32.SetCursorPos(left + args.x, top + args.y)
        modifiers = [VK[value] for value in (args.modifiers or [])]
        for key in modifiers:
            key_event(key)
        try:
            mouse_input(MOUSEEVENTF_LEFTDOWN)
            mouse_input(MOUSEEVENTF_LEFTUP)
        finally:
            for key in reversed(modifiers):
                key_event(key, True)
        if args.action == "click-paste":
            if args.text is None:
                raise RuntimeError("--text required")
            time.sleep(0.15)
            paste_text(args.text, hwnd)
        elif args.action == "click-replace":
            if args.text is None:
                raise RuntimeError("--text required")
            time.sleep(0.15)
            press_chord(["CTRL", "A"])
            time.sleep(0.08)
            paste_text(args.text, hwnd)
        elif args.action == "click-type":
            if args.text is None:
                raise RuntimeError("--text required")
            time.sleep(0.15)
            type_virtual_text(args.text)
    elif args.action == "scroll":
        if args.x is None or args.y is None or args.delta is None:
            raise RuntimeError("--x/--y/--delta required")
        left, top, _right, _bottom = rect(hwnd)
        user32.SetCursorPos(left + args.x, top + args.y)
        mouse_input(MOUSEEVENTF_WHEEL, args.delta)
    time.sleep(args.wait)

    observed = int(user32.GetForegroundWindow())
    capture(observed, args.out.resolve(), args.full_screen)
    cursor = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(cursor))
    print(
        json.dumps(
            {
                "status": "ok",
                "target_hwnd": hwnd,
                "foreground_hwnd": observed,
                "foreground_title": window_title(observed),
                "rect": rect(observed),
                "cursor": [cursor.x, cursor.y],
                "screenshot": str(args.out.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
