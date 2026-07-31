# ModDB Tracker

Tracks your ModDB mods/addons/files: downloads (total + today), visits, watchers,
rank, comments and replies. Charts and Windows toast notifications.

## Setup

```powershell
cd C:\Users\shero\Desktop\moddb_tracker
.venv\Scripts\pip install -r requirements.txt
```

## Configure

Edit `config.json`:

- `profile_url` — your ModDB member page, e.g. `https://www.moddb.com/members/yourname`
- `auto_discover: true` — scan your member profile's mods, addons and downloads tabs
- or list mod URLs manually in `mods`

## First run

```powershell
.venv\Scripts\python tracker.py --init
```

Discovers your content, stores a baseline snapshot and writes charts to `output\`.

## GUI

```powershell
.venv\Scripts\python gui.py
# background mode (no window, tray only):
.venv\Scripts\python gui.py --minimized
```

PyQt6 desktop app with:

- **Dashboard** — all charts rendered in the window (auto-rescales to fit)
- **Mods** — latest stats per item; double-click a row to open its ModDB page
- **History** — per-item snapshot table with day-over-day delta
- **Comments / Events** — all comments and notification events
- **Settings** — edit `config.json` from the UI (profile, poll interval, toggles)
- **Log** — live log output
- Toolbar buttons: **Poll now**, **Rescan profile**, **Refresh**, **Regenerate charts**
- **Auto-poll** checkbox in the status bar polls every `interval_minutes`

### System tray / background mode

- The app adds a tray icon (right-click: Show/Hide, Poll now, Rescan, Quit).
- Closing the window minimizes to the tray by default — polling and toast
  notifications keep running. Use **Quit** in the tray menu to exit.
- `--minimized` (or the Settings checkbox) starts it hidden in the tray.
- Left-click the tray icon to open/close the window; hover shows member + last poll.

Polls run in a background thread, so the UI stays responsive; toasts still fire.
The GUI and the CLI share the same SQLite DB, so you can use either (or both).

## Daily use

| Command | What it does |
| --- | --- |
| `--poll` | Fetch one cycle, detect new downloads/comments/replies, show toasts, update charts |
| `--report` | Print a stats table |
| `--charts` | Regenerate charts only |
| `--discover` | Re-scan your profile for new mods |
| `--poll --notify-off` | Poll without notifications |
| `--install-scheduler` | Create a Task Scheduler job (every N min per `poll.interval_minutes`) |
| `--remove-scheduler` | Remove that job |

## Charts (`output\`)

- `downloads_per_day.png` — daily download gain per item
- `total_downloads.png` — cumulative totals over time
- `mod_overview.png` — current total vs today per item
- `comment_activity.png` — comments/replies per day
- `dashboard.png` — 2x2 summary

## Notes

- ModDB is behind Cloudflare; the app impersonates Chrome via `curl_cffi` and warms
  up on the homepage first. It can be slow to respond at times — that's ModDB, not a bug.
- Toasts need an interactive (logged-in) Windows session; the scheduled task runs
  `pythonw` so no console window pops up every poll.
