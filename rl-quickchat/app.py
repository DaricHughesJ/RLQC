"""Standalone Rocket League quick-chat tray app."""

from __future__ import annotations

import ctypes
import json
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox, ttk

import pywintypes
import win32api
import win32clipboard
import win32con
import win32gui
import win32process
from PIL import Image, ImageDraw
from pynput import keyboard
from pystray import Icon, Menu, MenuItem

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
CHAT_LIMIT = 120
RL_TITLE = "rocket league"

CHANNELS = ("team", "all", "party")

DEFAULT_CONFIG = {
    "channel": "team",
    "chat_keys": {"all": "t", "team": "y", "party": "p"},
    "popup_hotkey": "ctrl+shift+enter",
    "open_delay_ms": 250,
    "char_delay_ms": 15,
    "presets": [
        {"hotkey": "ctrl+1", "text": "What a save!"},
        {"hotkey": "ctrl+2", "text": "Nice shot!"},
        {"hotkey": "ctrl+3", "text": "Great pass!"},
        {"hotkey": "ctrl+4", "text": "Thanks!"},
        {"hotkey": "ctrl+5", "text": "Sorry!"},
        {"hotkey": "ctrl+6", "text": "No problem."},
        {"hotkey": "ctrl+7", "text": "Close one!"},
        {"hotkey": "ctrl+8", "text": "Defending..."},
        {"hotkey": "ctrl+9", "text": "I got it!"},
    ],
}

SPECIAL_HOTKEYS = {
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "shift": "<shift>",
    "alt": "<alt>",
    "win": "<cmd>",
    "cmd": "<cmd>",
    "enter": "<enter>",
    "return": "<enter>",
    "esc": "<esc>",
    "escape": "<esc>",
    "space": "<space>",
    "tab": "<tab>",
    "backspace": "<backspace>",
    "delete": "<delete>",
    "insert": "<insert>",
    "up": "<up>",
    "down": "<down>",
    "left": "<left>",
    "right": "<right>",
    "home": "<home>",
    "end": "<end>",
    "pageup": "<page_up>",
    "pagedown": "<page_down>",
}

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_RETURN = 0x0D
VK_V = 0x56
MODIFIER_VKS = (
    VK_SHIFT,
    VK_CONTROL,
    VK_MENU,
    VK_LWIN,
    VK_RWIN,
    VK_LSHIFT,
    VK_RSHIFT,
    VK_LCONTROL,
    VK_RCONTROL,
    VK_LMENU,
    VK_RMENU,
)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class INPUTUNION(ctypes.Union):
    _fields_ = (("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT))


class INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("union", INPUTUNION))


user32 = ctypes.windll.user32
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
user32.VkKeyScanW.restype = ctypes.c_short


def _send_inputs(events: list[INPUT]) -> None:
    count = len(events)
    array = (INPUT * count)(*events)
    user32.SendInput(count, array, ctypes.sizeof(INPUT))


def _key_event(vk: int, flags: int, scan: int = 0) -> INPUT:
    return INPUT(
        type=INPUT_KEYBOARD,
        union=INPUTUNION(
            ki=KEYBDINPUT(
                wVk=vk,
                wScan=scan,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )


def _scan_for(vk: int) -> int:
    return user32.MapVirtualKeyW(vk, 0)


def tap_vk(vk: int) -> None:
    """Scancode tap — what Rocket League's action bindings actually see."""
    scan = _scan_for(vk)
    _send_inputs([_key_event(0, KEYEVENTF_SCANCODE, scan)])
    time.sleep(0.012)
    _send_inputs([_key_event(0, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, scan)])


def tap_vk_text(vk: int) -> None:
    """Virtual-key tap — generates WM_CHAR for the chat text box."""
    scan = _scan_for(vk)
    _send_inputs([_key_event(vk, 0, scan)])
    time.sleep(0.008)
    _send_inputs([_key_event(vk, KEYEVENTF_KEYUP, scan)])


def _vk_down(vk: int) -> None:
    _send_inputs([_key_event(vk, 0, _scan_for(vk))])


def _vk_up(vk: int) -> None:
    _send_inputs([_key_event(vk, KEYEVENTF_KEYUP, _scan_for(vk))])


def release_modifiers() -> None:
    events = []
    for vk in MODIFIER_VKS:
        scan = _scan_for(vk)
        events.append(_key_event(vk, KEYEVENTF_KEYUP, scan))
        events.append(_key_event(vk, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, scan))
    _send_inputs(events)


def wait_hotkey_released(timeout: float = 0.8) -> None:
    wait_vks = (
        *MODIFIER_VKS,
        VK_RETURN,
        *range(0x30, 0x3A),
        *range(0x60, 0x6A),
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in wait_vks):
            time.sleep(0.03)
            return
        time.sleep(0.01)


def tap_chat_key(key: str) -> None:
    ch = (key or "t").strip()[:1] or "t"
    result = user32.VkKeyScanW(ch)
    if result == -1:
        tap_vk(ord(ch.upper()))
        return
    tap_vk(result & 0xFF)


def set_clipboard_text(text: str) -> str | None:
    previous = None
    for _ in range(6):
        try:
            win32clipboard.OpenClipboard()
            try:
                try:
                    previous = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                except TypeError:
                    previous = None
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
            return previous
        except pywintypes.error:
            time.sleep(0.02)
    return None


def restore_clipboard(text: str | None) -> None:
    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            if text is not None:
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
    except pywintypes.error:
        pass


def paste_clipboard() -> None:
    _vk_down(VK_LCONTROL)
    time.sleep(0.012)
    tap_vk_text(VK_V)
    time.sleep(0.012)
    _vk_up(VK_LCONTROL)


def type_text(text: str, char_delay_ms: int) -> None:
    delay = max(0, char_delay_ms) / 1000.0
    for char in text:
        result = user32.VkKeyScanW(char)
        if result == -1:
            code = ord(char)
            if code <= 0xFFFF:
                _send_inputs(
                    [
                        _key_event(0, KEYEVENTF_UNICODE, code),
                        _key_event(0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, code),
                    ]
                )
            if delay:
                time.sleep(delay)
            continue
        vk = result & 0xFF
        need_shift = bool((result >> 8) & 0x01)
        if need_shift:
            _vk_down(VK_LSHIFT)
            time.sleep(0.008)
        tap_vk_text(vk)
        if need_shift:
            _vk_up(VK_LSHIFT)
        if delay:
            time.sleep(delay)


def find_rocket_league_hwnd() -> int | None:
    matches: list[int] = []

    def enum_cb(hwnd: int, _ctx: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if RL_TITLE in title.lower():
            matches.append(hwnd)
        return True

    win32gui.EnumWindows(enum_cb, None)
    if not matches:
        return None
    foreground = win32gui.GetForegroundWindow()
    if foreground in matches:
        return foreground

    def area(hwnd: int) -> int:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return max(0, right - left) * max(0, bottom - top)

    return max(matches, key=area)


def rocket_league_is_focused() -> tuple[int | None, bool]:
    hwnd = find_rocket_league_hwnd()
    if hwnd is None:
        return None, False
    return hwnd, win32gui.GetForegroundWindow() == hwnd


def focus_window(hwnd: int) -> bool:
    try:
        foreground = win32gui.GetForegroundWindow()
        fg_thread, _ = win32process.GetWindowThreadProcessId(foreground)
        this_thread = win32api.GetCurrentThreadId()
        attached = False
        if fg_thread != this_thread:
            attached = bool(win32process.AttachThreadInput(fg_thread, this_thread, True))
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        if attached:
            win32process.AttachThreadInput(fg_thread, this_thread, False)
    except pywintypes.error:
        return False
    return win32gui.GetForegroundWindow() == hwnd


def to_pynput(combo: str) -> str:
    parts: list[str] = []
    for raw in combo.lower().split("+"):
        key = raw.strip()
        if not key:
            continue
        if key in SPECIAL_HOTKEYS:
            parts.append(SPECIAL_HOTKEYS[key])
        elif key.startswith("f") and key[1:].isdigit():
            parts.append(f"<{key}>")
        elif len(key) == 1:
            parts.append(key)
        else:
            parts.append(f"<{key}>")
    return "+".join(parts)


PAD_BUTTONS = (
    (0x0001, "dpad_up"),
    (0x0002, "dpad_down"),
    (0x0004, "dpad_left"),
    (0x0008, "dpad_right"),
    (0x0010, "start"),
    (0x0020, "back"),
    (0x0040, "ls"),
    (0x0080, "rs"),
    (0x0100, "lb"),
    (0x0200, "rb"),
    (0x1000, "a"),
    (0x2000, "b"),
    (0x4000, "x"),
    (0x8000, "y"),
)
PAD_ORDER = [name for _mask, name in PAD_BUTTONS] + ["lt", "rt"]
TRIGGER_THRESHOLD = 80
MODIFIER_NAMES = {"ctrl", "shift", "alt", "win"}


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = (
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", wintypes.SHORT),
        ("sThumbLY", wintypes.SHORT),
        ("sThumbRX", wintypes.SHORT),
        ("sThumbRY", wintypes.SHORT),
    )


class XINPUT_STATE(ctypes.Structure):
    _fields_ = (("dwPacketNumber", wintypes.DWORD), ("Gamepad", XINPUT_GAMEPAD))


def load_xinput() -> ctypes.WinDLL | None:
    for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
        try:
            dll = ctypes.WinDLL(name)
            dll.XInputGetState.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)]
            dll.XInputGetState.restype = wintypes.DWORD
            return dll
        except OSError:
            continue
    return None


XINPUT = load_xinput()
if XINPUT is not None:
    try:
        XINPUT.XInputEnable.argtypes = [wintypes.BOOL]
        XINPUT.XInputEnable.restype = None
        XINPUT.XInputEnable(True)
    except (AttributeError, OSError):
        pass


def read_pad_buttons() -> frozenset[str]:
    if XINPUT is None:
        return frozenset()
    names: set[str] = set()
    state = XINPUT_STATE()
    for index in range(4):
        if XINPUT.XInputGetState(index, ctypes.byref(state)) != 0:
            continue
        gamepad = state.Gamepad
        for mask, name in PAD_BUTTONS:
            if gamepad.wButtons & mask:
                names.add(name)
        if gamepad.bLeftTrigger >= TRIGGER_THRESHOLD:
            names.add("lt")
        if gamepad.bRightTrigger >= TRIGGER_THRESHOLD:
            names.add("rt")
    return frozenset(names)


def is_pad_hotkey(hotkey: str) -> bool:
    return hotkey.strip().lower().startswith("pad:")


def parse_pad(hotkey: str) -> frozenset[str]:
    raw = hotkey.strip().lower()
    if not raw.startswith("pad:"):
        return frozenset()
    return frozenset(part for part in raw[4:].split("+") if part in PAD_ORDER)


def format_pad(buttons: set[str] | frozenset[str]) -> str:
    return "pad:" + "+".join(name for name in PAD_ORDER if name in buttons)


def hotkey_id(hotkey: str) -> str:
    raw = hotkey.strip().lower()
    if is_pad_hotkey(raw):
        return format_pad(parse_pad(raw))
    return to_pynput(raw)


def pynput_key_name(key: object) -> str | None:
    key_map = {
        keyboard.Key.ctrl: "ctrl",
        keyboard.Key.ctrl_l: "ctrl",
        keyboard.Key.ctrl_r: "ctrl",
        keyboard.Key.shift: "shift",
        keyboard.Key.shift_l: "shift",
        keyboard.Key.shift_r: "shift",
        keyboard.Key.alt: "alt",
        keyboard.Key.alt_l: "alt",
        keyboard.Key.alt_r: "alt",
        keyboard.Key.alt_gr: "alt",
        keyboard.Key.cmd: "win",
        keyboard.Key.cmd_l: "win",
        keyboard.Key.cmd_r: "win",
    }
    if key in key_map:
        return key_map[key]
    if isinstance(key, keyboard.Key):
        name = str(key.name).lower()
        if name.endswith("_l") or name.endswith("_r"):
            name = name[:-2]
        return name.replace("_", "")
    char = getattr(key, "char", None)
    if char and ord(char) >= 32:
        return char.lower()
    vk = getattr(key, "vk", None)
    if isinstance(vk, int) and 0x30 <= vk <= 0x39:
        return chr(vk)
    return None


def format_keyboard_combo(mods: set[str], key: str) -> str:
    order = ("ctrl", "alt", "shift", "win")
    parts = [name for name in order if name in mods]
    parts.append(key)
    return "+".join(parts)


def normalize_message(text: str) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:CHAT_LIMIT]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    chat_keys = dict(DEFAULT_CONFIG["chat_keys"])
    chat_keys.update(data.get("chat_keys") or {})
    merged["chat_keys"] = chat_keys
    if merged.get("channel") not in CHANNELS:
        merged["channel"] = "team"
    presets = []
    for item in data.get("presets") or DEFAULT_CONFIG["presets"]:
        if not isinstance(item, dict):
            continue
        hotkey = str(item.get("hotkey") or "").strip()
        text = str(item.get("text") or "").strip()
        if hotkey and text:
            presets.append({"hotkey": hotkey, "text": text})
    merged["presets"] = presets or list(DEFAULT_CONFIG["presets"])
    return merged


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def make_tray_image() -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 6, 60, 46), radius=12, fill=(47, 158, 255, 255))
    draw.polygon([(18, 44), (28, 62), (38, 44)], fill=(47, 158, 255, 255))
    draw.ellipse((16, 20, 24, 28), fill=(255, 255, 255, 255))
    draw.ellipse((28, 20, 36, 28), fill=(255, 255, 255, 255))
    draw.ellipse((40, 20, 48, 28), fill=(255, 255, 255, 255))
    return image


class QuickChatApp:
    def __init__(self) -> None:
        self.config = load_config()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("RL Quick Chat")
        self.icon: Icon | None = None
        self.listener: keyboard.GlobalHotKeys | None = None
        self.popup: tk.Toplevel | None = None
        self.editor: tk.Toplevel | None = None
        self.send_lock = threading.Lock()
        self._recording = False
        self._record_var: tk.StringVar | None = None
        self._record_overlay: tk.Toplevel | None = None
        self._record_listener: keyboard.Listener | None = None
        self._record_held_mods: set[str] = set()
        self._record_pad_prev: frozenset[str] = frozenset()
        self._record_pad_captured: set[str] = set()
        self._record_pad_until = 0.0
        self._pad_bindings: list[tuple[frozenset[str], object]] = []
        self._pad_prev: frozenset[str] = frozenset()
        self._pad_stop = threading.Event()
        self._pad_lockout = 0.0
        self._set_dpi_aware()

    @staticmethod
    def _set_dpi_aware() -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            try:
                user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

    def run(self) -> None:
        self._start_hotkeys()
        threading.Thread(target=self._pad_loop, daemon=True).start()
        self.icon = Icon("RL Quick Chat", make_tray_image(), "RL Quick Chat", self._menu())
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self.root.mainloop()
        self.shutdown()

    def shutdown(self) -> None:
        self._pad_stop.set()
        self._cancel_record()
        self._stop_hotkeys()
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass

    def _notify(self, message: str) -> None:
        if self.icon is not None:
            try:
                self.icon.notify(message, "RL Quick Chat")
            except Exception:
                pass

    def _menu(self) -> Menu:
        def channel_item(channel: str) -> MenuItem:
            label = channel.title()

            def activate(_icon: Icon, _item: MenuItem) -> None:
                self.set_channel(channel)

            def checked(_item: MenuItem) -> bool:
                return self.config.get("channel") == channel

            return MenuItem(label, activate, checked=checked, radio=True)

        return Menu(
            MenuItem("Quick message...", self._tray_popup, default=True),
            Menu.SEPARATOR,
            MenuItem(
                "Channel",
                Menu(*(channel_item(channel) for channel in CHANNELS)),
            ),
            MenuItem("Edit presets", self._tray_editor),
            Menu.SEPARATOR,
            MenuItem("Exit", self._tray_exit),
        )

    def set_channel(self, channel: str) -> None:
        if channel not in CHANNELS:
            return
        self.config["channel"] = channel
        save_config(self.config)
        if self.icon is not None:
            self.icon.update_menu()

    def _start_hotkeys(self) -> None:
        self._stop_hotkeys()
        mapping: dict[str, object] = {}
        pad_bindings: list[tuple[frozenset[str], object]] = []

        def bind(hotkey: str, action: object) -> None:
            if is_pad_hotkey(hotkey):
                required = parse_pad(hotkey)
                if required:
                    pad_bindings.append((required, action))
                return
            combo = to_pynput(hotkey)
            if combo and combo not in mapping:
                mapping[combo] = action

        bind(str(self.config.get("popup_hotkey") or "ctrl+shift+enter"), self._on_popup_hotkey)
        for preset in self.config.get("presets") or []:
            text = preset["text"]
            if is_pad_hotkey(preset["hotkey"]):
                bind(preset["hotkey"], lambda t=text: self._on_pad_hotkey(t))
            else:
                bind(preset["hotkey"], lambda t=text: self._on_preset_hotkey(t))
        self._pad_bindings = pad_bindings
        if not mapping:
            return
        try:
            self.listener = keyboard.GlobalHotKeys(mapping)
            self.listener.start()
        except Exception as exc:
            self.listener = None
            error_msg = str(exc)
            self.root.after(0, lambda e=error_msg: self._notify(f"Hotkey error: {e}"))

    def _stop_hotkeys(self) -> None:
        if self.listener is None:
            return
        try:
            self.listener.stop()
        except Exception:
            pass
        self.listener = None

    def _on_preset_hotkey(self, text: str) -> None:
        if self._recording:
            return
        threading.Thread(target=self.send_chat, args=(text, False, False), daemon=True).start()

    def _on_pad_hotkey(self, text: str) -> None:
        if self._recording:
            return
        self.root.after(0, lambda t=text: self.send_chat(t, True, True))

    def _on_popup_hotkey(self) -> None:
        if self._recording:
            return
        self.root.after(0, self.show_popup)

    def _pad_loop(self) -> None:
        while not self._pad_stop.wait(0.008):
            buttons = read_pad_buttons()
            if self._recording:
                self._record_pad_tick(buttons)
                self._pad_prev = buttons
                continue
            now = time.time()
            if now < self._pad_lockout:
                self._pad_prev = buttons
                continue
            newly = buttons - self._pad_prev
            matches = [
                (required, action)
                for required, action in self._pad_bindings
                if required <= buttons and newly & required
            ]
            if matches:
                _required, action = max(matches, key=lambda item: len(item[0]))
                self._pad_lockout = now + 0.55
                action()  # type: ignore[operator]
            self._pad_prev = buttons

    def _record_pad_tick(self, buttons: frozenset[str]) -> None:
        now = time.time()
        newly = buttons - self._record_pad_prev
        if newly and self._record_pad_until <= 0:
            self._record_pad_captured = set(newly)
            self._record_pad_until = now + 0.18
        elif self._record_pad_until > 0:
            self._record_pad_captured |= set(newly)
            if now >= self._record_pad_until and self._record_pad_captured:
                combo = format_pad(self._record_pad_captured)
                self.root.after(0, lambda c=combo: self._finish_record(c))
        self._record_pad_prev = buttons

    def begin_record(self, target: tk.StringVar, parent: tk.Misc) -> None:
        if self._recording:
            self._cancel_record()
        self._recording = True
        self._record_var = target
        self._record_held_mods = set()
        self._record_pad_prev = read_pad_buttons()
        self._record_pad_captured = set()
        self._record_pad_until = 0.0

        overlay = tk.Toplevel(parent)
        self._record_overlay = overlay
        overlay.title("Record hotkey")
        overlay.attributes("-topmost", True)
        overlay.configure(bg="#111827")
        overlay.resizable(False, False)
        tk.Label(
            overlay,
            text="Press a keyboard combo or controller button",
            fg="#f9fafb",
            bg="#111827",
            font=("Segoe UI", 12, "bold"),
        ).pack(padx=24, pady=(18, 6))
        tk.Label(
            overlay,
            text="Esc cancels  ·  Hold two pad buttons for a combo",
            fg="#9ca3af",
            bg="#111827",
            font=("Segoe UI", 9),
        ).pack(padx=24, pady=(0, 18))
        overlay.protocol("WM_DELETE_WINDOW", self._cancel_record)
        overlay.bind("<Escape>", lambda _e: self._cancel_record())
        overlay.grab_set()
        overlay.focus_force()

        def on_press(key: object) -> None:
            name = pynput_key_name(key)
            if name is None:
                return
            if key == keyboard.Key.esc:
                self.root.after(0, self._cancel_record)
                return
            if name in MODIFIER_NAMES:
                self._record_held_mods.add(name)
                return
            combo = format_keyboard_combo(set(self._record_held_mods), name)
            self.root.after(0, lambda c=combo: self._finish_record(c))

        def on_release(key: object) -> None:
            name = pynput_key_name(key)
            if name in MODIFIER_NAMES:
                self._record_held_mods.discard(name)

        self._record_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._record_listener.start()

    def _finish_record(self, combo: str) -> None:
        if not self._recording:
            return
        if self._record_var is not None:
            self._record_var.set(combo)
        self._cancel_record()

    def _cancel_record(self) -> None:
        self._recording = False
        self._record_var = None
        self._record_pad_until = 0.0
        self._record_pad_captured = set()
        listener = self._record_listener
        self._record_listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
        overlay = self._record_overlay
        self._record_overlay = None
        if overlay is not None:
            try:
                overlay.grab_release()
                overlay.destroy()
            except tk.TclError:
                pass

    def _tray_popup(self, _icon: Icon, _item: MenuItem) -> None:
        self.root.after(0, lambda: self.show_popup(require_focus=False))

    def _tray_editor(self, _icon: Icon, _item: MenuItem) -> None:
        self.root.after(0, self.show_editor)

    def _tray_exit(self, _icon: Icon, _item: MenuItem) -> None:
        self.root.after(0, self._exit)

    def _exit(self) -> None:
        self.shutdown()
        self.root.destroy()

    def send_chat(self, text: str, restore_focus: bool, from_controller: bool = False) -> None:
        message = normalize_message(text)
        if not message:
            return
        with self.send_lock:
            hwnd, focused = rocket_league_is_focused()
            if hwnd is None:
                self._notify("Rocket League is not running.")
                return
            if from_controller or restore_focus:
                if not focused:
                    focus_window(hwnd)
                    time.sleep(0.08)
            elif not focused:
                return

            channel = self.config.get("channel") or "team"
            chat_key = str((self.config.get("chat_keys") or {}).get(channel) or "t")
            open_delay = max(0, int(self.config.get("open_delay_ms") or 250)) / 1000.0

            char_delay = int(self.config.get("char_delay_ms") or 15)

            if not from_controller:
                wait_hotkey_released()
            release_modifiers()
            
            time.sleep(0.02)
            tap_chat_key(chat_key)
            time.sleep(open_delay)
            release_modifiers()
            type_text(message, char_delay)
            time.sleep(0.04)
            tap_vk(VK_RETURN)

    def show_popup(self, require_focus: bool = True) -> None:
        hwnd, focused = rocket_league_is_focused()
        if hwnd is None:
            self._notify("Rocket League is not running.")
            return
        if require_focus and not focused:
            return
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.lift()
            self.popup.focus_force()
            return

        popup = tk.Toplevel(self.root)
        self.popup = popup
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#111827")

        frame = tk.Frame(popup, bg="#111827", padx=12, pady=10)
        frame.pack()
        tk.Label(
            frame,
            text="Type a message  ·  Enter to send  ·  Esc to cancel",
            fg="#9ca3af",
            bg="#111827",
            font=("Segoe UI", 9),
        ).pack(anchor="w")
        entry = tk.Entry(
            frame,
            width=42,
            font=("Segoe UI", 13),
            bg="#1f2937",
            fg="#f9fafb",
            insertbackground="#f9fafb",
            relief="flat",
        )
        entry.pack(fill="x", pady=(8, 0), ipady=6)

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        popup.update_idletasks()
        width = popup.winfo_reqwidth()
        x = left + max(0, (right - left - width) // 2)
        y = top + max(40, (bottom - top) // 3)
        popup.geometry(f"+{x}+{y}")
        entry.focus_force()

        def close() -> None:
            if self.popup is popup:
                self.popup = None
            popup.destroy()

        def send(_event: object | None = None) -> None:
            message = entry.get()
            close()
            threading.Thread(target=self.send_chat, args=(message, True), daemon=True).start()

        entry.bind("<Return>", send)
        entry.bind("<Escape>", lambda _e: close())

    def show_editor(self) -> None:
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.lift()
            self.editor.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.editor = win
        win.title("Edit presets")
        win.configure(bg="#111827")
        win.resizable(True, True)
        win.attributes("-topmost", True)

        pad = {"padx": 12, "pady": 8}
        tk.Label(
            win,
            text="Popup hotkey",
            fg="#e5e7eb",
            bg="#111827",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", **pad)
        popup_var = tk.StringVar(value=str(self.config.get("popup_hotkey") or ""))
        tk.Entry(win, textvariable=popup_var, width=22, font=("Segoe UI", 11)).grid(
            row=0, column=1, sticky="w", **pad
        )
        ttk.Button(
            win,
            text="Record",
            command=lambda: self.begin_record(popup_var, win),
        ).grid(row=0, column=2, sticky="w", padx=(0, 12), pady=8)
        tk.Label(
            win,
            text="Click Record, then press a keyboard combo or a controller button.",
            fg="#9ca3af",
            bg="#111827",
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=12)

        table = tk.Frame(win, bg="#111827")
        table.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=12, pady=4)
        win.grid_rowconfigure(2, weight=1)
        win.grid_columnconfigure(1, weight=1)

        tk.Label(table, text="Hotkey", fg="#9ca3af", bg="#111827").grid(row=0, column=0, sticky="w")
        tk.Label(table, text="Message", fg="#9ca3af", bg="#111827").grid(row=0, column=2, sticky="w")

        rows: list[tuple[tk.StringVar, tk.StringVar]] = []

        def add_row(hotkey: str = "", text: str = "") -> None:
            row_index = len(rows) + 1
            hotkey_var = tk.StringVar(value=hotkey)
            text_var = tk.StringVar(value=text)
            tk.Entry(table, textvariable=hotkey_var, width=18).grid(
                row=row_index, column=0, padx=(0, 8), pady=3, sticky="w"
            )
            ttk.Button(
                table,
                text="Record",
                command=lambda var=hotkey_var: self.begin_record(var, win),
            ).grid(row=row_index, column=1, padx=(0, 8), pady=3)
            tk.Entry(table, textvariable=text_var, width=40).grid(
                row=row_index, column=2, pady=3, sticky="ew"
            )
            rows.append((hotkey_var, text_var))

        table.grid_columnconfigure(2, weight=1)
        for preset in self.config.get("presets") or []:
            add_row(preset["hotkey"], preset["text"])

        def save() -> None:
            presets = []
            seen: set[str] = set()
            popup_hotkey = popup_var.get().strip().lower()
            if not popup_hotkey:
                messagebox.showerror("Invalid hotkey", "Popup hotkey cannot be empty.", parent=win)
                return
            seen.add(hotkey_id(popup_hotkey))
            for hotkey_var, text_var in rows:
                hotkey = hotkey_var.get().strip().lower()
                text = text_var.get().strip()
                if not hotkey and not text:
                    continue
                if not hotkey or not text:
                    messagebox.showerror(
                        "Incomplete preset",
                        "Each preset needs both a hotkey and a message.",
                        parent=win,
                    )
                    return
                combo = hotkey_id(hotkey)
                if combo in seen:
                    messagebox.showerror(
                        "Duplicate hotkey",
                        f"Hotkey already used: {hotkey}",
                        parent=win,
                    )
                    return
                seen.add(combo)
                presets.append({"hotkey": hotkey, "text": text})
            if not presets:
                messagebox.showerror("No presets", "Add at least one preset.", parent=win)
                return
            self.config["popup_hotkey"] = popup_hotkey
            self.config["presets"] = presets
            save_config(self.config)
            self._start_hotkeys()
            close()

        def close() -> None:
            self._cancel_record()
            if self.editor is win:
                self.editor = None
            win.destroy()

        buttons = tk.Frame(win, bg="#111827")
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew", padx=12, pady=10)
        ttk.Button(buttons, text="Add preset", command=lambda: add_row()).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=close).pack(side="right")
        ttk.Button(buttons, text="Save", command=save).pack(side="right", padx=(0, 8))
        win.protocol("WM_DELETE_WINDOW", close)


def main() -> int:
    QuickChatApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
