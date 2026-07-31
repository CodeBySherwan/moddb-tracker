# ModDB Tracker UI/UX Implementation Plan

Maps the design doc (ModDB Tracker UIUX Redesign Plan v2) onto concrete,
codebase-level changes. Implemented in phases so the app stays shippable at
every step.

## Phase 1 — Visual identity + core UX (this pass)

### Theme (`charts.py`, `gui.py`)
- New palette: BG `#0F172A`, cards `#1E293B`, secondary panels `#273449`,
  borders `#334155`, text `#E2E8F0`, muted `#94A3B8`, accent blue `#3B82F6`,
  success green `#22C55E`, warning orange `#F59E0B`, error red `#EF4444`.
- Recolour all matplotlib charts + dashboard to match (currently amber).
- Rewrite the Qt stylesheet: softer radii, larger padding, hover states,
  accent-selected sidebar items.

### Window layout (`gui.py`)
- **Top bar**: logo mark + "ModDB Tracker", global search box (filters the
  active page), Refresh button, last-sync label, busy/"Checking ModDB…" state.
- **Sidebar**: iconified navigation (Dashboard / My Mods / Analytics /
  Comments / Notifications / Configuration / Log) with hover + selected states.
- **Status bar**: last sync, database size, app version, auto-poll toggle.

### Dashboard (`dashboard.py` widgets inside `gui.py`)
- Row of **stat cards** (Total, Today, This week, This month, Avg/day,
  Comments, Replies, Fastest-growing mod, Tracked mods) with big numbers,
  colored ▲/▼ deltas and a count-up animation.
- **Activity feed** panel (events: downloads/comments/replies, colour-coded,
  newest first).
- Charts section below (existing PNGs, re-themed).

### My Mods (`mod_card.py` widgets inside `gui.py`)
- Replace the table with **mod cards** in a responsive flow layout.
- Each card: name, type badge, downloads/today, watchers/visits, last check,
  comment count, favourite star, and actions (Open page, Refresh, More).
- Toolbar: search filter, sort (name/downloads/today), favourites first.
- Context menu: Refresh, Open, Copy URL, Favourite, Export, Remove.
- Per-mod refresh in a background worker; favourite + remove persist in the DB.

### Comments / Events
- Comments: filter (All / Replies), open-on-double-click, reply action that
  opens the conversation on ModDB.
- Events: filterable, colour-coded by kind.

### Polish
- Empty states ("No tracked mods — click Rescan profile to begin").
- Relative timestamps ("2 min ago").
- Spinner/busy text instead of a frozen UI (workers already threaded).

## Phase 2 — Analytics + interactivity (next pass)

- **Analytics page**: top mods, growth comparison, weekly/monthly/cumulative
  charts, moving average, growth %, best day/week ever, milestones, estimate
  of next week's downloads.  ✅ `analytics.py` (pure functions) + `AnalyticsPage`
  in `gui.py`: mod selector, 30/60/90-day range, stat cards, per-day bars +
  7-day moving average, cumulative totals (with milestone markers), weekly
  bars; all-mod aggregate view with per-mod cumulative comparison.
- **Interactive charts** via `pyqtgraph` (zoom/pan/hover) replacing static
  matplotlib images on the Analytics page.  ✅ hover readouts, drag-to-zoom,
  PNG chart export.
- **Notification center**: bell with unread badge, per-category history,
  "reply now / ignore" actions.  ✅ `events.seen` column + badge in top bar,
  kind filter, mark-all-read (on page visit or via bell), double-click /
  context-menu "Open on ModDB".
- **Export**: CSV + JSON (already have JSON), Excel + PDF report.  ✅ Export
  menu in the top bar: CSV (4 sheets), Excel (openpyxl, 4 tabs), PDF report
  (reportlab), JSON.
- **Favourites/sorting preferences** persisted.  ✅ new `ui` config section:
  `mods_sort`, `mods_filter` (debounced), `analytics_days`.

## Phase 3 — Advanced (future)

- Dashboard widget rearrangement, search across all data, achievements +
  milestones timeline, AI insights ("downloads up 37% vs last week"), hourly
  downloads, country stats, Steam-like profile.

### Phase 3 progress
- **Compare two mods** ✅ `ComparePage` in `gui.py` + `analytics.aligned_totals`:
  two mod selectors (auto-sync so A ≠ B), 30/60/90-day range, head-to-head
  stats table (winner highlighted green), cumulative overlay chart, daily-gain
  chart, and a "daily advantage" diff chart; PNG export.

## Architecture

The current flat modules already give clean boundaries
(`transport` / `storage` / `tracker` / `charts` / `notify` / `gui`). Phase 1
keeps this structure; GUI widgets are added as clear classes. A package
split (`ui/` + `backend/`) is deferred to a dedicated refactor pass so the
redesign ships without breaking the working CLI, scheduler and DB.
