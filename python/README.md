# lalafo-mcp (Python)

FastMCP implementation of the Lalafo search + Carcheck MCP server.
See the [repository root README](../README.md) for the project overview and rationale.

## Tools

| Tool | Description |
|------|-------------|
| `check_fines(plate)` | Normalizes a KG plate and returns Carcheck links (official) + mashina.kg / tolom.kg / balance.kg. Carcheck is gated by login + reCAPTCHA, so this is an assistant — the user completes login and the captcha. |
| `search(query, per_page, strict)` | Keyword search. `strict=True` drops irrelevant padding (Lalafo optimizes recall, not precision) and ranks by relevance. |
| `search_cars(make, model, year_from, price_max_usd)` | Car search. Handles 3 API quirks: brand = category, year = numeric range, and price is normalized to USD client-side (the server price filter is currency-blind). |
| `search_rentals(rooms, price_max, district, deal, exclude_shared)` | Apartment rentals: rooms, price in KGS som, district matched in text (no structured filter exists), room-shares («подселение») filtered out. |
| `subscribe(name, kind, …)` | Save a search (`kind` = `search`/`cars`/`rentals`); existing matches are marked seen so only **new** listings notify. |
| `list_subscriptions()` / `unsubscribe(id)` | Manage saved searches. |
| `check_subscriptions(id?)` | Return listings new since the last check and push notifications. |

## Run

Requires Python 3.10+. [uv](https://docs.astral.sh/uv/) is recommended.

```bash
cd python
uv sync                 # or: pip install -e .
uv run lalafo-mcp       # start the MCP server (stdio)
```

Optionally copy `.env.example` → `.env` and set `LALAFO_COUNTRY_ID`
(12 = Kyrgyzstan), `LALAFO_LANGUAGE`, `USD_KGS_RATE`.

### Connect to Claude Code

```bash
claude mcp add lalafo-kg -- uv run --directory /ABS/PATH/lalafo-mcp/python lalafo-mcp
```

(Without uv: `pip install -e .`, then run `lalafo-mcp` or `python -m lalafo_mcp.server`.)

## Self-test (no MCP client)

```bash
python selftest.py      # hits the live API: check_fines + search + search_cars + search_rentals
```

## Subscriptions & notifications

Save a search via the `subscribe` tool, then poll for new matches — on demand
(`check_subscriptions`) or headless:

```bash
lalafo-mcp-monitor            # loop every MONITOR_INTERVAL seconds (default 600)
lalafo-mcp-monitor --once     # single pass — for cron / Windows Task Scheduler
```

State persists under `LALAFO_DATA_DIR` (default `~/.lalafo-mcp/subscriptions.json`) and is shared
with the server. Notifications go to any configured channel — `NTFY_TOPIC_URL`,
`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`, `WEBHOOK_URL`; with none set, `check_subscriptions`
just returns the new matches.

## Notes / limitations

- **Carcheck cannot be automated**: a government service behind login + reCAPTCHA (backend `/api/violation-check/find-by-plate` → 401 without a session). The tool only normalizes the plate and builds the links.
- **License plates are not published in Lalafo listings** — for `check_fines`, get the plate from the seller / photos.
- **Car prices are normalized to USD client-side** — the server `price[to]` compares the raw number, mixing `$` and som. The rate is set via `USD_KGS_RATE`.
- **Silent filter ignore**: Lalafo silently drops an invalid filter (no error). `search_cars` / `search_rentals` verify that the filter actually narrowed the result set and return a `warning` otherwise.
- Use within the platforms' Terms of Service; avoid aggressive request rates.

## Layout

```
src/lalafo_mcp/
  client.py     # Lalafo API (stdlib urllib) with retry: /v3/ads/search, /v3/ads/{id}
  core.py       # logic: search_listings, search_cars, search_rentals (mcp-free, testable)
  carcheck.py       # plate normalization + link generation
  subscriptions.py  # saved searches: persistence + new-listing detection
  notify.py         # notification channels (ntfy / Telegram / webhook)
  monitor.py        # headless polling loop (lalafo-mcp-monitor)
  server.py         # FastMCP wrappers (search/cars/rentals/fines + subscribe/check)
selftest.py         # live smoke test
```
