# Keystroke & System Monitor Toolkit

A lightweight Windows monitoring toolkit for capturing keystrokes, clipboard activity, active applications, and live system resource usage. Each monitor streams updates to its own dashboard HTML file and saves logs locally for later review.

## What this project includes

- **Keylogger** — records typed keys and broadcasts them live
- **Clipboard monitor** — detects copied text, URLs, emails, numbers, and longer content
- **App tracker** — tracks the foreground application and session usage time
- **System monitor** — reports CPU, RAM, disk, network, and top processes

## Project files

- `keylogger.py` — keystroke capture server
- `clipboard_monitor.py` — clipboard watcher
- `app_tracker.py` — active app and usage tracker
- `system_monitor.py` — live system stats monitor
- `keylogger_dashboard.html` — dashboard for keystrokes
- `clipboard_dashboard.html` — dashboard for clipboard activity
- `app_dashboard.html` — dashboard for app usage
- `system_dashboard.html` — dashboard for system stats
- `keylog.txt` — keystroke log output
- `clipboard_log.txt` — clipboard log output
- `app_usage_log.json` — app usage session history

## Features

- Real-time WebSocket updates to browser dashboards
- Local log persistence to text/JSON files
- Simple startup flow with one Python process per monitor
- Built for Windows environments, especially for the app tracker

## Requirements

- Python 3.9+ recommended
- Windows 10/11 (recommended for full functionality)

Install the required packages:

```bash
pip install pynput pyperclip psutil pywin32 websockets
```

> Note: `pywin32` is required for the app tracker to detect active windows.

## Quick start

### 1) Start the keylogger

```bash
python keylogger.py
```

Open `keylogger_dashboard.html` in your browser.

### 2) Start the clipboard monitor

```bash
python clipboard_monitor.py
```

Open `clipboard_dashboard.html` in your browser.

### 3) Start the app tracker

```bash
python app_tracker.py
```

Open `app_dashboard.html` in your browser.

### 4) Start the system monitor

```bash
python system_monitor.py
```

Open `system_dashboard.html` in your browser.

## How it works

Each monitor runs as its own Python script and uses WebSockets to push updates to a matching dashboard HTML page. The dashboard receives JSON data from the server and renders the information in the browser.

## Logs and output

- `keylog.txt` — typed key events
- `clipboard_log.txt` — copied content and clipboard metadata
- `app_usage_log.json` — application usage summaries and session history

## Privacy and responsibility

This toolkit captures user activity and system data. Use it only on systems you own or have explicit permission to monitor. Respect local laws, company policy, and user privacy requirements.

## Troubleshooting

- If a dashboard does not update, confirm the matching monitor is running.
- If `pywin32` is missing, install it with `pip install pywin32`.
- If the clipboard monitor does not detect changes, ensure `pyperclip` is installed.
- If a monitor stops unexpectedly, check the terminal output for the error message and fix the dependency or permission issue.

## Recommended usage

Run each monitor in its own terminal window so the dashboards remain responsive and easy to inspect.
