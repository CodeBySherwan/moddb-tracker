"""Windows toast notifications for the tracker.

Backed by `winotify`, which shells out to PowerShell and the WindowsRuntime
toast API -- no pywin32 needed and it works fine from a scheduled task as
long as the task runs in your interactive session.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, Optional

from winotify import Notification

logger = logging.getLogger("tracker.notify")

DEFAULT_APP_ID = "ModDB Tracker"


def _write_icon(icon_path: Path) -> None:
    """Generate a small PNG icon for toasts if it does not exist yet."""
    if icon_path.exists():
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:  # pragma: no cover
        return
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    size = 96
    img = Image.new("RGB", (size, size), "#1a1a1a")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, size - 4, size - 4], radius=16, fill="#f0c040")
    try:
        font = ImageFont.truetype("arialbd.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    text = "MDB"
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), text, fill="#1a1a1a", font=font)
    img.save(icon_path)


def _icon_path(config: dict) -> Optional[str]:
    try:
        out_dir = Path(config.get("output_dir", "output"))
        icon = out_dir / "icons" / "tracker.png"
        _write_icon(icon)
        return str(icon.resolve())
    except Exception:  # noqa: BLE001 - icon is cosmetic
        return None


def toast(title: str, message: str, launch: Optional[str] = None, config: Optional[dict] = None) -> None:
    """Show a single Windows toast (best-effort; failures are logged, not fatal)."""
    config = config or {}
    try:
        notif = Notification(
            app_id=config.get("app_id", DEFAULT_APP_ID),
            title=title,
            msg=message,
            icon=_icon_path(config),
            duration="short",
            launch=launch or "",
        )
        notif.show()
        logger.info("TOAST: %s - %s", title, message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Toast failed (%s): %s", type(exc).__name__, exc)


def notify_events(events: Iterable[dict], config: dict) -> None:
    """Fire one toast per event, capped so we never spam more than a few."""
    events = list(events)
    if not events:
        return

    max_toasts = int(config.get("notifications", {}).get("max_toasts", 5))
    shown = events[:max_toasts]
    rest = len(events) - len(shown)

    for ev in shown:
        toast(ev["title"], ev["message"], launch=ev.get("url"), config=config)

    if rest > 0:
        toast(
            f"{rest} more update{'s' if rest != 1 else ''}",
            "Check the tracker report for details.",
            config=config,
        )
