"""HTTP transport for ModDB.

ModDB sits behind Cloudflare. The `moddb` package ships a `requests`-based
session that Cloudflare 403s in practice, while `curl_cffi` with a Chrome
TLS/HTTP2 fingerprint sails through -- as long as we do NOT override the
User-Agent (a mismatched UA makes Cloudflare block the request).

This module provides a `get_page` replacement and patches the `moddb`
package's internal `get_page` references so the library's parsing helpers
(comments, files, member mods, ...) keep working unchanged.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from curl_cffi import requests as cfr

logger = logging.getLogger("tracker.transport")

_session: Optional[cfr.Session] = None
_session_warmed_at: float = 0.0

REQUEST_DELAY = 0.5
MAX_ATTEMPTS = 4

# Cloudflare's clearance cookie is short-lived; re-warm before it expires.
COOKIE_TTL = 15 * 60  # seconds


def _reset_session() -> None:
    """Drop the current session so the next request re-creates and re-warms."""
    global _session, _session_warmed_at
    if _session is not None:
        try:
            _session.close()
        except Exception:  # noqa: BLE001
            pass
        _session = None
    _session_warmed_at = 0.0


def _is_challenge(resp: Any) -> bool:
    """True if the response is a Cloudflare 'Just a moment' challenge."""
    if resp.status_code not in (403, 503):
        return False
    try:
        return "Just a moment" in resp.text
    except Exception:  # noqa: BLE001
        return True


def get_session() -> cfr.Session:
    """Create (or refresh) the curl_cffi session.

    A fresh session is frequently Cloudflare-challenged on member pages, but a
    quick visit to the homepage grants a clearance cookie that makes the rest
    of the site accessible, so we warm the session up on first use -- and again
    whenever the cookie may have expired.
    """
    global _session, _session_warmed_at
    if _session is None or (time.time() - _session_warmed_at) > COOKIE_TTL:
        _reset_session()
        _session = cfr.Session(impersonate="chrome")
        for attempt in range(4):
            try:
                resp = _session.get("https://www.moddb.com", timeout=30)
                if _is_challenge(resp):
                    raise RuntimeError(f"homepage challenge (HTTP {resp.status_code})")
                resp.raise_for_status()
                _session_warmed_at = time.time()
                logger.info("Warmed up ModDB session (homepage HTTP %d)", resp.status_code)
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Warm-up attempt %d failed: %s", attempt + 1, exc)
                time.sleep(2)
        time.sleep(REQUEST_DELAY)
    return _session


def get_page(url: str, *, params: Optional[Dict[str, Any]] = None, json: bool = False) -> Any:
    """Fetch `url` and return a BeautifulSoup object (or parsed JSON).

    Mirrors the signature of ``moddb.utils.get_page`` so it can be patched in.
    """
    session = get_session()
    params = dict(params) if params else None

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        session = get_session()
        try:
            resp = session.get(url, params=params, timeout=30)
            if _is_challenge(resp):
                raise RuntimeError(f"Cloudflare challenge (HTTP {resp.status_code}) for {url}")
            resp.raise_for_status()
            if json:
                return resp.json()
            import moddb

            return moddb.soup(resp.text)
        except Exception as exc:  # noqa: BLE001 - be resilient, retry then surface
            last_error = exc
            logger.warning("Request failed for %s (attempt %d/%d): %s", url, attempt, MAX_ATTEMPTS, exc)
            _reset_session()  # cookie may have expired -> next attempt re-warms
            time.sleep(2 * attempt)

        time.sleep(REQUEST_DELAY)

    raise RuntimeError(f"Failed to fetch {url} after {MAX_ATTEMPTS} attempts: {last_error}")


def patch_moddb() -> None:
    """Point every moddb module at our Cloudflare-proof get_page."""
    import moddb
    from moddb import base as moddb_base
    from moddb import boxes as moddb_boxes
    from moddb import utils as moddb_utils
    from moddb.pages import base as pages_base
    from moddb.pages import entity as pages_entity
    from moddb.pages import file as pages_file
    from moddb.pages import fp as pages_fp
    from moddb.pages import mixins as pages_mixins

    for module in (
        moddb_base,
        moddb_boxes,
        moddb_utils,
        pages_base,
        pages_entity,
        pages_file,
        pages_fp,
        pages_mixins,
    ):
        module.get_page = get_page

    logger.info("Patched moddb transport with curl_cffi get_page")


def friendly_url(url: str) -> str:
    return url.split("?")[0].rstrip("/")
