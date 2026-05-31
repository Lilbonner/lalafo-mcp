"""Thin Lalafo API client (stdlib only — no third-party deps).

Verified facts encoded here:
  - Base host is api.lalafo.com, search path /v3/ads/search (NO /api prefix).
  - No auth token needed, but country-id / device / language headers are mandatory
    (omitting them returns HTTP 417).
"""
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.lalafo.com"
_RETRY_HTTP = {429, 500, 502, 503, 504}


def _headers() -> dict:
    return {
        "country-id": os.getenv("LALAFO_COUNTRY_ID", "12"),
        "device": "pc",
        "language": os.getenv("LALAFO_LANGUAGE", "ru"),
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
    }


def _get(path: str, params: dict | None = None, timeout: float = 25.0, retries: int = 3) -> dict:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_headers())
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            # retry only transient server/rate-limit codes; surface 4xx immediately
            if e.code in _RETRY_HTTP and attempt < retries - 1:
                last = e
            else:
                raise
        except (urllib.error.URLError, ConnectionResetError, socket.timeout, TimeoutError) as e:
            # transient network issues (e.g. WinError 10054 connection reset)
            last = e
            if attempt == retries - 1:
                raise
        time.sleep(0.6 * (attempt + 1))
    raise last  # pragma: no cover


class LalafoClient:
    def search(self, params: dict) -> dict:
        """GET /v3/ads/search -> {'items': [...], 'total': int}."""
        merged = {"page": 1, "per-page": 20, "expand": "url"}
        merged.update(params)
        data = _get("/v3/ads/search", merged)
        return {
            "items": data.get("items", []),
            "total": (data.get("_meta") or {}).get("totalCount"),
        }

    def detail(self, ad_id: int) -> dict:
        """GET /v3/ads/{id} -> full ad with structured `params`."""
        return _get(f"/v3/ads/{ad_id}")
