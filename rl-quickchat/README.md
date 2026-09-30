# RL Quick Chat

Standalone Windows tray app that sends custom Rocket League chat instantly.

It types into the in-game chat box (open chat → type → Enter). It does not inject into the game or change Rocket League files.

## Install

```powershell
cd C:\Users\dARIC\rl-quickchat
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python app.py
```

A chat-bubble icon appears in the system tray. Right-click it for channel, presets, and Exit.

## Usage

- **Presets:** `Ctrl+1` through `Ctrl+9` send the saved lines (only while Rocket League is focused).
- **Type anything:** `Ctrl+Shift+Enter` (or left-click the tray icon) opens a tiny box. Type a message, Enter sends, Esc cancels.
- **Channel:** Team (`Y`), All (`T`), or Party (`P`) from the tray menu. Change these keys in `config.json` if your bindings differ.
- **Edit / record presets:** tray → Edit presets. Click **Record**, then press a keyboard combo or a controller button. Save when you are done.
- **Controller:** Xbox pads and most Steam Input controllers work. PlayStation pads usually need Steam Input enabled. Avoid binding the D-pad if you still want Rocket League's built-in quick chat. Combos like `LB + Y` are fine.

## Rocket League settings

Use **borderless** or **windowed** mode. Exclusive fullscreen often ignores simulated keystrokes.

The app only sends while Rocket League is the foreground window, so messages do not leak into Discord or a browser. The type-anything popup is allowed to take focus briefly, then it returns to the game before sending.

## Config

[`config.json`](config.json) next to `app.py`:

- `channel`: `team`, `all`, or `party`
- `chat_keys`: in-game keys that open each chat channel
- `popup_hotkey`: hotkey for the type-anything box
- `open_delay_ms`: wait after opening chat before typing
- `presets`: list of `{ "hotkey", "text" }`
