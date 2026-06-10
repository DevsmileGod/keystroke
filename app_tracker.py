"""
app_tracker.py — App Usage Tracker with WebSocket Server
=========================================================
Tracks which application window is active and for how long.
Sends live updates to the dashboard every second.

Requirements:
    pip install pywin32 websockets

Usage:
    python app_tracker.py

Then open app_dashboard.html in your browser.
Session data is saved to app_usage_log.json
"""

import asyncio
import json
import datetime
import threading
import time
from pathlib import Path
from collections import defaultdict
import websockets

try:
    import win32gui
    import win32process
    import psutil
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("[!] pywin32 not found. Install with: pip install pywin32")

# ── Config ──────────────────────────────────────────────────
WS_HOST      = "localhost"
WS_PORT      = 8768
POLL_SEC     = 1.0
LOG_FILE     = Path("app_usage_log.json")

# ── State ────────────────────────────────────────────────────
connected_clients: set = set()
loop: asyncio.AbstractEventLoop = None

# Usage data: { app_name: seconds }
usage_data: dict = defaultdict(float)
# Per-app timeline: { app_name: [ {start, end, title} ] }
timeline: dict   = defaultdict(list)

current_app   = ""
current_title = ""
current_start = time.time()
session_start = time.time()


# ── Window detection ─────────────────────────────────────────
def get_active_app() -> tuple:
    """Return (app_name, window_title)"""
    if not WIN32_AVAILABLE:
        return "Unknown", "pywin32 not installed"
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        name = proc.name().replace(".exe","")
        return name, title
    except Exception:
        return "Unknown", ""


# ── Build payload ────────────────────────────────────────────
def build_payload() -> dict:
    now = time.time()
    # include current ongoing session
    tmp = dict(usage_data)
    if current_app:
        tmp[current_app] = tmp.get(current_app, 0) + (now - current_start)

    total_sec = sum(tmp.values()) or 1
    apps = []
    for name, secs in sorted(tmp.items(), key=lambda x: x[1], reverse=True)[:10]:
        apps.append({
            "name":    name,
            "seconds": round(secs),
            "percent": round(secs / total_sec * 100, 1),
            "hms":     fmt_hms(secs),
        })

    return {
        "timestamp":    datetime.datetime.now().strftime("%H:%M:%S"),
        "current_app":  current_app,
        "current_title": current_title[:60],
        "session_secs": round(now - session_start),
        "total_apps":   len(tmp),
        "apps":         apps,
    }


def fmt_hms(s: float) -> str:
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    if h:   return f"{h}h {m}m"
    if m:   return f"{m}m {s}s"
    return f"{s}s"


# ── Tracker loop ─────────────────────────────────────────────
def tracker_loop():
    global current_app, current_title, current_start

    while True:
        app, title = get_active_app()

        if app != current_app:
            # Save time for previous app
            if current_app:
                elapsed = time.time() - current_start
                usage_data[current_app] += elapsed
                timeline[current_app].append({
                    "start": current_start,
                    "end":   time.time(),
                    "title": current_title,
                })

            current_app   = app
            current_title = title
            current_start = time.time()
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ▶ {app}  —  {title[:50]}")

        # Broadcast
        payload = build_payload()
        broadcast(payload)

        time.sleep(POLL_SEC)


# ── Broadcast ─────────────────────────────────────────────────
def broadcast(data: dict):
    if loop is None or not connected_clients:
        return
    payload = json.dumps(data)
    asyncio.run_coroutine_threadsafe(_broadcast(payload), loop)


async def _broadcast(payload: str):
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send(payload)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


# ── Save session ──────────────────────────────────────────────
def save_session():
    data = {
        "date":    datetime.date.today().isoformat(),
        "usage":   dict(usage_data),
        "timeline": {k: v for k, v in timeline.items()},
    }
    with LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── WebSocket handler ─────────────────────────────────────────
async def handler(websocket):
    connected_clients.add(websocket)
    print(f"[WS] Client connected ({len(connected_clients)} total)")
    try:
        await websocket.send(json.dumps(build_payload()))
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)


async def main():
    global loop
    loop = asyncio.get_running_loop()

    t = threading.Thread(target=tracker_loop, daemon=True)
    t.start()

    print(f"[*] App Tracker started.")
    print(f"[*] WebSocket on  ws://{WS_HOST}:{WS_PORT}")
    print("[*] Open app_dashboard.html in your browser.")
    print("[*] Press Ctrl+C to stop.\n")

    try:
        async with websockets.serve(handler, WS_HOST, WS_PORT):
            await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        usage_data[current_app] = usage_data.get(current_app, 0) + (time.time() - current_start)
        save_session()
        print(f"\n[*] Session saved to {LOG_FILE.resolve()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
