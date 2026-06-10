"""
clipboard_monitor.py — Windows Clipboard Monitor with WebSocket Server
=======================================================================
Watches the clipboard every 0.5s and broadcasts any new content
to connected WebSocket clients (the dashboard).

Requirements:
    pip install pyperclip websockets

Usage:
    python clipboard_monitor.py

Then open clipboard_dashboard.html in your browser.
All clipboard entries are also saved to clipboard_log.txt
"""

import asyncio
import json
import datetime
import threading
import time
from pathlib import Path
import pyperclip
import websockets

# ── Config ──────────────────────────────────────────────────
WS_HOST   = "localhost"
WS_PORT   = 8766          # different port from keylogger (8765)
LOG_FILE  = Path("clipboard_log.txt")
POLL_SEC  = 0.5           # how often to check clipboard

# ── State ────────────────────────────────────────────────────
connected_clients: set = set()
loop: asyncio.AbstractEventLoop = None
last_content: str = ""


# ── Helpers ──────────────────────────────────────────────────
def detect_type(text: str) -> str:
    """Guess the content type of the clipboard text."""
    t = text.strip()
    if t.startswith("http://") or t.startswith("https://"):
        return "url"
    if "\n" in t and len(t) > 120:
        return "code"
    if "@" in t and "." in t and " " not in t:
        return "email"
    if any(c.isdigit() for c in t) and len(t) < 30 and t.replace(" ","").replace("-","").replace("+","").isdigit():
        return "number"
    if len(t) > 200:
        return "paragraph"
    return "text"


def build_entry(text: str) -> dict:
    now = datetime.datetime.now()
    return {
        "content":   text,
        "type":      detect_type(text),
        "length":    len(text),
        "timestamp": now.strftime("%H:%M:%S"),
        "date":      now.strftime("%Y-%m-%d"),
        "preview":   text[:120].replace("\n", " ") + ("…" if len(text) > 120 else ""),
    }


def append_to_log(entry: dict):
    sep = "─" * 60
    line = (
        f"\n[{entry['date']} {entry['timestamp']}] "
        f"type={entry['type']}  len={entry['length']}\n"
        f"{entry['content']}\n{sep}\n"
    )
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def broadcast(entry: dict):
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


# ── Clipboard poller ─────────────────────────────────────────
def poll_clipboard():
    global last_content
    print("[*] Clipboard polling started…")
    while True:
        try:
            current = pyperclip.paste()
            if current and current != last_content:
                last_content = current
                entry = build_entry(current)
                append_to_log(entry)
                broadcast(entry)
                preview = entry["preview"][:60]
                print(f"[{entry['timestamp']}] [{entry['type'].upper()}] {preview}")
        except Exception as e:
            print(f"[!] Clipboard read error: {e}")
        time.sleep(POLL_SEC)


# ── WebSocket server ─────────────────────────────────────────
async def handler(websocket):
    connected_clients.add(websocket)
    print(f"[WS] Client connected  ({len(connected_clients)} total)")
    try:
        # Send connection confirmation
        await websocket.send(json.dumps({
            "content":   "Clipboard Monitor connected and watching…",
            "type":      "system",
            "length":    0,
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "date":      datetime.datetime.now().strftime("%Y-%m-%d"),
            "preview":   "● LIVE",
        }))
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Client disconnected ({len(connected_clients)} total)")


async def main():
    global loop
    loop = asyncio.get_running_loop()

    t = threading.Thread(target=poll_clipboard, daemon=True)
    t.start()

    print(f"[*] Clipboard Monitor started.  Log → {LOG_FILE.resolve()}")
    print(f"[*] WebSocket on  ws://{WS_HOST}:{WS_PORT}")
    print("[*] Open clipboard_dashboard.html in your browser.")
    print("[*] Press Ctrl+C to stop.\n")

    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
