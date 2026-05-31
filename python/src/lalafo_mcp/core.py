"""Business logic (mcp-free, so it is unit-testable on its own).

Encodes the verified Lalafo quirks:
  - Search is "recall over precision": q= maps to a category and pads the feed, so we
    re-filter client-side (all query tokens must appear) for `search_listings(strict=True)`.
  - Cars are categorized BY BRAND (make == category_id); model is matched on the title.
  - Year is a NUMERIC range param: parameters[62][from]=<literal year> (NOT a value_id).
  - The price filter is CURRENCY-BLIND, so car prices are normalized to USD client-side
    (use `price` when symbol is $, else national_price / USD_KGS_RATE).
  - A wrong/absent structured filter is SILENTLY IGNORED, so we assert it narrowed.
"""
import os
import re
import time

from .client import LalafoClient

_client = LalafoClient()

# Cars are categorized by brand. Verified: Dodge = 1566. Unknown makes resolve dynamically.
_MAKE_CATEGORY = {
    "dodge": 1566,
}

_YEAR_PARAM = "parameters[62][from]"  # numeric range, literal year

# --- Rentals (verified) ---
_RENTAL_CATEGORY = {"long": 2044, "daily": 2045}  # Долгосрочная / Посуточная аренда квартир
_ROOMS_PARAM = "parameters[69]"                    # «Количество комнат» (categorical -> value_id)
_ROOM_VALUE = {"1": 2773, "2": 2774, "3": 2775, "4": 2776,
               "студия": 15496, "studio": 15496, "0": 15496}
# Markers of room-shares (подселение): the «N комнат» param also tags these, so drop by text.
_SHARED_MARKERS = ("подселение", "подселением", "подсилен", "подселен", "подселять",
                   "одна комната", "для девуш", "для девоч", "для парн", "койко")


def _tokens(s: str) -> list[str]:
    return [t for t in re.sub(r"[^0-9a-zA-Zа-яА-Я]+", " ", (s or "").lower()).split() if len(t) > 1]


def _abs_url(u):
    if not u:
        return None
    return u if u.startswith("http") else "https://lalafo.kg" + u


def _to_usd(item: dict, rate: float):
    if item.get("symbol") == "$" or item.get("currency") == "USD":
        return item.get("price")
    np = item.get("national_price") or {}
    price = np.get("price") if isinstance(np, dict) else None
    return round(price / rate) if price else None


def _resolve_make_category(make: str):
    key = make.strip().lower()
    if key in _MAKE_CATEGORY:
        return _MAKE_CATEGORY[key]
    # Dynamic: search the make and take the dominant category among car-like listings.
    res = _client.search({"q": make, "per-page": 40})
    counts: dict = {}
    for i in res["items"]:
        title = (i.get("title") or "")
        if title.lower().startswith(key) and re.search(r"(19|20)\d\d\s*г", title):
            cat = i.get("category_id")
            counts[cat] = counts.get(cat, 0) + 1
    return max(counts, key=counts.get) if counts else None


def _narrow_warning(category_id: int, total: int, what: str) -> str:
    """Warn when a structured filter was silently ignored (totalCount didn't shrink)."""
    base = _client.search({"category_id": category_id, "per-page": 1})["total"]
    if total == base:
        return f"Фильтр по {what} мог не примениться (totalCount не изменился)."
    return ""


def _district_matcher(district: str):
    """Build a predicate over (title+description). Lalafo has no district param, so we
    match microdistricts in text: '7 микрорайон' / '7 мкр' / 'мкр 7' (not 17/27),
    or fall back to all-tokens for named districts ('Джал', 'Восток-5')."""
    d = (district or "").strip().lower()
    if not d:
        return lambda hay: True
    num = re.search(r"\d+", d)
    if num and re.search(r"мкр|мкрн|микрорайон|мрн|\bмк\b", d):
        n = num.group(0)
        rx = re.compile(
            rf"(?<!\d){n}\s*-?\s*(?:мкр|мкрн|мк|мрн|микрорайон)"
            rf"|(?:мкр|мкрн|мк|мрн|микрорайон)\s*-?\s*{n}(?!\d)", re.I)
        return lambda hay: bool(rx.search(hay))
    toks = _tokens(d)
    return lambda hay: all(t in hay for t in toks)


def search_rentals(rooms: str = "", price_max: int = 0, district: str = "",
                   deal: str = "long", exclude_shared: bool = True,
                   per_page: int = 50, max_scan: int = 200) -> dict:
    cat = _RENTAL_CATEGORY.get((deal or "long").strip().lower())
    if not cat:
        return {"error": f"Неизвестный тип сделки '{deal}'. Используйте 'long' или 'daily'."}

    params = {"category_id": cat, "expand": "url,description", "per-page": per_page}
    room_vid = None
    if str(rooms).strip():
        room_vid = _ROOM_VALUE.get(str(rooms).strip().lower())
        if room_vid is None:
            return {"error": f"Не знаю value_id для комнат='{rooms}'. Доступно: 1-4 или 'студия'."}
        params[_ROOMS_PARAM] = room_vid
    if price_max:
        params["price[from]"] = 0
        params["price[to]"] = price_max

    first = _client.search({**params, "page": 1})
    total = first["total"]
    warning = _narrow_warning(cat, total, "комнатам") if room_vid is not None else ""

    match_district = _district_matcher(district)
    rows, seen, scanned, page, items = [], set(), 0, 1, first["items"]
    while items and scanned < max_scan:
        for i in items:
            if i.get("id") in seen:
                continue
            seen.add(i.get("id"))
            scanned += 1
            hay = (i.get("title", "") + " " + (i.get("description") or "")).lower()
            if exclude_shared and any(m in hay for m in _SHARED_MARKERS):
                continue
            if not match_district(hay):
                continue
            rows.append({
                "id": i.get("id"),
                "title": i.get("title"),
                "price": i.get("price"),
                "currency": i.get("symbol") or i.get("currency"),
                "city": i.get("city"),
                "url": _abs_url(i.get("url")),
            })
        if scanned >= (total or 0) or scanned >= max_scan:
            break
        page += 1
        time.sleep(0.25)  # light pacing between paginated requests (politeness / fewer resets)
        items = _client.search({**params, "page": page})["items"]

    rows.sort(key=lambda r: (r["price"] is None, r["price"] or 0))
    result = {
        "deal": deal,
        "category_id": cat,
        "rooms": rooms or "any",
        "total_matching_server_filters": total,  # после category+rooms+price
        "scanned": scanned,
        "count": len(rows),                       # после текст-фильтров (район/подселение)
        "items": rows,
    }
    if district:
        result["district_filter"] = district
        result["note"] = "Район отфильтрован по тексту; объявления без слова о районе могли не попасть."
    if warning:
        result["warning"] = warning
    return result


def search_listings(query: str, per_page: int = 30, strict: bool = True) -> list[dict]:
    res = _client.search({"q": query, "per-page": per_page, "expand": "url,description"})
    toks = _tokens(query)
    out, seen = [], set()
    for i in res["items"]:
        if i.get("id") in seen:
            continue
        seen.add(i.get("id"))
        hay = (i.get("title", "") + " " + (i.get("description") or "")).lower()
        cov = sum(t in hay for t in toks) / max(len(toks), 1)
        # strict drops only the pure "mishmash" (0 query tokens); partial matches are kept
        # and ranked by coverage, so abbreviated titles like "наушники koss" survive.
        if strict and cov == 0:
            continue
        out.append({
            "id": i.get("id"),
            "title": i.get("title"),
            "price": i.get("price"),
            "currency": i.get("symbol") or i.get("currency"),
            "city": i.get("city"),
            "relevance": round(cov, 2),
            "url": _abs_url(i.get("url")),
        })
    out.sort(key=lambda x: -x["relevance"])
    return out


def search_cars(make: str, model: str = "", year_from: int | None = None,
                price_max_usd: int | None = None, per_page: int = 50) -> dict:
    cat = _resolve_make_category(make)
    if not cat:
        return {"error": f"Не удалось определить категорию для марки '{make}'. Уточните название."}

    params = {"category_id": cat, "per-page": per_page, "expand": "url"}
    if year_from:
        params[_YEAR_PARAM] = year_from
    res = _client.search(params)

    warning = _narrow_warning(cat, res["total"], "году") if year_from else ""

    rate = float(os.getenv("USD_KGS_RATE", "89"))
    mtoks = _tokens(model)
    rows, seen = [], set()
    for i in res["items"]:
        if i.get("id") in seen:
            continue
        seen.add(i.get("id"))
        title = i.get("title", "") or ""
        if mtoks and not all(t in title.lower() for t in mtoks):
            continue
        usd = _to_usd(i, rate)
        if price_max_usd and (usd is None or usd > price_max_usd):
            continue
        yr = re.search(r"(19|20)\d\d", title)
        rows.append({
            "id": i.get("id"),
            "title": title,
            "price_usd": usd,
            "price_raw": f"{i.get('price')} {i.get('symbol')}",
            "year": int(yr.group(0)) if yr else None,
            "url": _abs_url(i.get("url")),
        })
    rows.sort(key=lambda r: (r["price_usd"] is None, r["price_usd"] or 0))

    result = {"make": make, "category_id": cat, "count": len(rows), "items": rows}
    if warning:
        result["warning"] = warning
    return result
