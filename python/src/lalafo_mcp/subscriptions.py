"""Saved-search subscriptions: persistence, execution and new-listing detection.

A subscription is a saved call to one of the search tools plus the set of listing ids
already seen. `check()` re-runs the search, reports listings whose id is new, updates the
seen set, and (optionally) pushes notifications. State is a JSON file under LALAFO_DATA_DIR
(default ~/.lalafo-mcp), so it is shared between the MCP server and the standalone monitor.
"""
import json
import os
import uuid
from datetime import datetime, timezone

from . import core, notify

_SEEN_CAP = 500  # cap stored ids per subscription to bound the file size


def _data_dir() -> str:
    d = os.getenv("LALAFO_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lalafo-mcp")
    os.makedirs(d, exist_ok=True)
    return d


def _store() -> str:
    return os.path.join(_data_dir(), "subscriptions.json")


def _load() -> list:
    p = _store()
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(subs) -> None:
    with open(_store(), "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(sub) -> list[dict]:
    """Execute the subscription's saved search; return current matching items (each has `id`)."""
    p = sub.get("params", {})
    kind = sub["kind"]
    if kind == "search":
        return core.search_listings(p.get("query", ""), p.get("per_page", 30), p.get("strict", True))
    if kind == "cars":
        return core.search_cars(p.get("make", ""), p.get("model", ""),
                                p.get("year_from") or None, p.get("price_max_usd") or None).get("items", [])
    if kind == "rentals":
        return core.search_rentals(p.get("rooms", ""), p.get("price_max", 0), p.get("district", ""),
                                   p.get("deal", "long"), p.get("exclude_shared", True)).get("items", [])
    return []


def _fmt(items) -> str:
    lines = []
    for it in items[:10]:
        price = it.get("price")
        cur = it.get("currency") or ""
        raw = it.get("price_raw")
        money = raw if raw else f"{price} {cur}".strip()
        lines.append(f"- {it.get('title')} | {money}\n  {it.get('url')}")
    if len(items) > 10:
        lines.append(f"… и ещё {len(items) - 10}")
    return "\n".join(lines)


def add(name: str, kind: str, params: dict) -> dict:
    if kind not in ("search", "cars", "rentals"):
        return {"error": "kind must be one of: search, cars, rentals"}
    sub = {
        "id": "sub_" + uuid.uuid4().hex[:8],
        "name": name, "kind": kind, "params": params,
        "seen_ids": [], "created_at": _now(), "last_checked": None,
    }
    # Seed with current results so only FUTURE listings trigger notifications.
    try:
        items = _run(sub)
        sub["seen_ids"] = [it["id"] for it in items if it.get("id")][:_SEEN_CAP]
        sub["last_checked"] = _now()
        seeded = len(sub["seen_ids"])
    except Exception as e:
        seeded, sub["seed_error"] = 0, str(e)
    subs = _load()
    subs.append(sub)
    _save(subs)
    return {"id": sub["id"], "name": name, "kind": kind, "seeded_existing": seeded,
            "channels": notify.configured_channels(),
            "message": "Подписка создана; отслеживаю новые подходящие объявления."}


def list_all() -> list[dict]:
    return [{"id": s["id"], "name": s["name"], "kind": s["kind"], "params": s.get("params", {}),
             "seen": len(s.get("seen_ids", [])), "last_checked": s.get("last_checked")}
            for s in _load()]


def remove(sub_id: str) -> dict:
    subs = _load()
    kept = [s for s in subs if s["id"] != sub_id]
    if len(kept) == len(subs):
        return {"error": f"Подписка {sub_id} не найдена"}
    _save(kept)
    return {"removed": sub_id}


def check(sub_id: str | None = None, notify_channels: bool = True) -> dict:
    """Run subscriptions, return listings new since last check, update state, maybe notify."""
    subs = _load()
    results, changed = [], False
    for s in subs:
        if sub_id and s["id"] != sub_id:
            continue
        try:
            items = _run(s)
        except Exception as e:
            results.append({"id": s["id"], "name": s["name"], "error": str(e)})
            continue
        seen = set(s.get("seen_ids", []))
        fresh = [it for it in items if it.get("id") and it["id"] not in seen]
        s["seen_ids"] = (list(seen) + [it["id"] for it in fresh])[-_SEEN_CAP:]
        s["last_checked"] = _now()
        changed = True
        notified = []
        if fresh and notify_channels:
            notified = notify.send(f"Lalafo: {len(fresh)} новых по «{s['name']}»", _fmt(fresh), fresh)
        results.append({"id": s["id"], "name": s["name"], "new_count": len(fresh),
                        "new_items": fresh, "notified": notified})
    if changed:
        _save(subs)
    return {"checked": len(results), "subscriptions": results}
