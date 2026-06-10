"""
system_monitor.py — System Health Monitor with WebSocket Server
===============================================================
Streams live CPU, RAM, Disk, and Network stats to the dashboard.

Requirements:
    pip install psutil websockets

Usage:
    python system_monitor.py

Then open system_dashboard.html in your browser.
"""

import asyncio
import json
import datetime
import threading
import time
from pathlib import Path
import psutil
import websockets

# ── Config ──────────────────────────────────────────────────
WS_HOST      = "localhost"
WS_PORT      = 8767
INTERVAL_SEC = 1.0   # update every second

# ── State ────────────────────────────────────────────────────
connected_clients: set = set()
loop: asyncio.AbstractEventLoop = None

# baseline network counters
_prev_net = psutil.net_io_counters()
_prev_net_time = time.time()


# ── Collect stats ─────────────────────────────────────────────
def collect() -> dict:
    global _prev_net, _prev_net_time

    # CPU
    cpu_total  = psutil.cpu_percent(interval=None)
    cpu_cores  = psutil.cpu_percent(interval=None, percpu=True)
    cpu_freq   = psutil.cpu_freq()
    cpu_count  = psutil.cpu_count(logical=True)

    # RAM
    ram = psutil.virtual_memory()

    # Disk
    disk        = psutil.disk_usage("/")
    disk_io     = psutil.disk_io_counters()

    # Network
    now_net      = psutil.net_io_counters()
    now_time     = time.time()
    elapsed      = now_time - _prev_net_time or 1
    bytes_sent   = (now_net.bytes_sent - _prev_net.bytes_sent) / elapsed
    bytes_recv   = (now_net.bytes_recv - _prev_net.bytes_recv) / elapsed
    _prev_net    = now_net
    _prev_net_time = now_time

    # Processes (top 5 by CPU)
    procs = []
    for p in sorted(psutil.process_iter(["pid","name","cpu_percent","memory_percent"]),
                    key=lambda x: x.info["cpu_percent"] or 0, reverse=True)[:5]:
        procs.append({
            "pid":  p.info["pid"],
            "name": p.info["name"][:22],
            "cpu":  round(p.info["cpu_percent"] or 0, 1),
            "mem":  round(p.info["memory_percent"] or 0, 1),
        })

    return {
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "cpu": {
            "total":  round(cpu_total, 1),
            "cores":  [round(c, 1) for c in cpu_cores],
            "freq":   round(cpu_freq.current, 0) if cpu_freq else 0,
            "count":  cpu_count,
        },
        "ram": {
            "percent": round(ram.percent, 1),
            "used_gb": round(ram.used / 1e9, 2),
            "total_gb":round(ram.total / 1e9, 2),
            "available_gb": round(ram.available / 1e9, 2),
        },
        "disk": {
            "percent":  round(disk.percent, 1),
            "used_gb":  round(disk.used / 1e9, 1),
            "total_gb": round(disk.total / 1e9, 1),
            "free_gb":  round(disk.free / 1e9, 1),
        },
        "network": {
            "sent_kb":  round(bytes_sent / 1024, 1),
            "recv_kb":  round(bytes_recv / 1024, 1),
            "total_sent_mb": round(now_net.bytes_sent / 1e6, 1),
            "total_recv_mb": round(now_net.bytes_recv / 1e6, 1),
        },
        "processes": procs,
    }


# ── Broadcast loop ────────────────────────────────────────────
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


def stats_loop():
    # warm up cpu_percent
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)
    time.sleep(0.5)
    while True:
        try:
            data = collect()
            broadcast(data)
            t = data["timestamp"]
            print(f"[{t}] CPU {data['cpu']['total']}%  "
                  f"RAM {data['ram']['percent']}%  "
                  f"↑{data['network']['sent_kb']} KB/s  "
                  f"↓{data['network']['recv_kb']} KB/s")
        except Exception as e:
            print(f"[!] Error: {e}")
        time.sleep(INTERVAL_SEC)


# ── WebSocket handler ─────────────────────────────────────────
async def handler(websocket):
    connected_clients.add(websocket)
    print(f"[WS] Client connected  ({len(connected_clients)} total)")
    try:
        # Send one snapshot immediately
        await websocket.send(json.dumps(collect()))
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Client disconnected ({len(connected_clients)} total)")


async def main():
    global loop
    loop = asyncio.get_running_loop()

    t = threading.Thread(target=stats_loop, daemon=True)
    t.start()

    print(f"[*] System Monitor started.")
    print(f"[*] WebSocket on  ws://{WS_HOST}:{WS_PORT}")
    print("[*] Open system_dashboard.html in your browser.")
    print("[*] Press Ctrl+C to stop.\n")

    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
