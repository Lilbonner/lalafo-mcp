# lalafo-mcp

> An MCP server that lets AI assistants search the **Lalafo** classifieds marketplace
> (Kyrgyzstan / Central Asia) in natural language, and assist with **Carcheck** vehicle
> fine/​history lookups.

Two interchangeable implementations of the same tools are included:

| | Directory | Stack | Run |
|---|---|---|---|
| **Python** | [`python/`](python/) | [FastMCP](https://github.com/modelcontextprotocol/python-sdk) (3.10+) | `uv run lalafo-mcp` |
| **Go** | [`go/`](go/) | [official Go MCP SDK](https://github.com/modelcontextprotocol/go-sdk) | `go build` → one static binary |

## What is this?

[Lalafo](https://lalafo.kg) is the largest online classifieds marketplace in Kyrgyzstan
(also operates in Azerbaijan, etc.). It has **no official public API**. This project wraps
Lalafo's internal JSON API as a small set of [Model Context Protocol](https://modelcontextprotocol.io)
tools, so any MCP-compatible assistant — Claude Code, Claude Desktop, … — can search
listings (products, cars, apartment rentals) conversationally. It also ships `check_fines`,
a helper for Kyrgyzstan's government **Carcheck** vehicle service.

## Why?

- **Lalafo has no API**, and its on-site search optimizes *recall over precision*: a query for
  a specific item returns a couple of real matches and then a flood of loosely-related padding
  and promoted ads. This server talks to the real endpoints and adds the client-side filtering
  needed to get **precise, ranked** results.
- **The data has traps that break naive queries** — the price filter is currency-blind,
  malformed structured filters are *silently ignored*, cars are categorized by brand, and
  microdistricts aren't a real filter. All handled here so the assistant gets correct answers.
- **Before buying a used car** you usually want to check its outstanding fines / legal status;
  `check_fines` turns a plate number into the right Carcheck links.

## Tools

| Tool | Description |
|---|---|
| `search(query, per_page?, strict?)` | Keyword search across all of Lalafo. `strict` (default `true`) drops irrelevant padding and ranks by relevance. |
| `search_cars(make, model?, year_from?, price_max_usd?)` | Car search: brand → category, year as a range, price normalized to **USD** (the raw filter mixes currencies). |
| `search_rentals(rooms?, price_max?, district?, deal?, exclude_shared?)` | Apartment rentals: rooms, price in **KGS som**, district matched in text, room-shares («подселение») filtered out. |
| `check_fines(plate)` | Normalizes a KG plate and returns ready Carcheck links (official + 3 mirrors). Carcheck needs login + reCAPTCHA, so the user finishes the lookup. |

## Subscriptions & notifications

Save any search and get notified when **new** matching listings appear. *(Python implementation; Go port pending.)*

| Tool | Description |
|---|---|
| `subscribe(name, kind, …)` | Save a search (`kind` = `search` / `cars` / `rentals`). Existing matches are marked as seen, so you're only alerted about **new** ones. |
| `list_subscriptions()` | List saved searches. |
| `unsubscribe(id)` | Delete a subscription. |
| `check_subscriptions(id?)` | Re-run subscriptions, return listings new since last check, and push notifications. |

Subscriptions persist under `LALAFO_DATA_DIR` (default `~/.lalafo-mcp`). Notifications are sent to
any configured channel — **ntfy** (`NTFY_TOPIC_URL`), **Telegram** (`TELEGRAM_BOT_TOKEN` +
`TELEGRAM_CHAT_ID`) or a **webhook** (`WEBHOOK_URL`); if none are set, `check_subscriptions` simply
returns the matches. Poll it two ways:

- **From the assistant** — call `check_subscriptions` on demand, or on a timer via Claude Code `/loop`.
- **Headless** — `lalafo-mcp-monitor` (loops every `MONITOR_INTERVAL` s) or `lalafo-mcp-monitor --once`
  for cron / Windows Task Scheduler. The monitor shares the subscription store with the server.

## Quick start

### Python
```bash
cd python
uv sync                 # or: pip install -e .
uv run lalafo-mcp       # starts the MCP server over stdio
python selftest.py      # optional: live smoke test against the real API
```

### Go
```bash
cd go
go build -o lalafo-mcp.exe .
./lalafo-mcp.exe        # starts the MCP server over stdio
go run . -selftest      # optional: live smoke test
```

### Connect to Claude Code
```bash
# Python
claude mcp add lalafo-kg -- uv run --directory /ABS/PATH/lalafo-mcp/python lalafo-mcp
# Go (single binary, no runtime needed)
claude mcp add lalafo-kg -- /ABS/PATH/lalafo-mcp/go/lalafo-mcp.exe
```
Then ask, e.g.: *“find a 2-room rental in the 7th microdistrict under 40000 som”* or
*“Dodge Ram from 2020 under \$30k”*.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `LALAFO_COUNTRY_ID` | `12` | `12` = Kyrgyzstan, `13` = Azerbaijan, `14` = Poland |
| `LALAFO_LANGUAGE` | `ru` | response language |
| `USD_KGS_RATE` | `89` | KGS per 1 USD, used to normalize car prices |

Copy `.env.example` → `.env` in `python/` or `go/` to override.

## Example

`search_cars(make="Dodge", model="Ram", year_from=2020, price_max_usd=30000)`:
```json
{
  "make": "Dodge", "category_id": 1566, "count": 3,
  "items": [
    { "title": "Dodge Ram 1500: 2022 г., Пикап", "price_usd": 28000, "year": 2022,
      "url": "https://lalafo.kg/bishkek/ads/...-id-110273428" }
  ]
}
```

## How it works (Lalafo API notes)

- Endpoint `https://api.lalafo.com/v3/ads/search` — **no auth token**, but the
  `country-id` / `device` / `language` headers are mandatory (otherwise HTTP 417).
- Select filters: `parameters[<id>]=<value_id>`. Numeric range (year): `parameters[62][from]=<year>`.
- The price filter is **currency-blind** → car prices are normalized to USD client-side.
- A malformed/unknown filter is **silently ignored** (no error) → the server checks that
  `totalCount` actually shrank and warns otherwise.
- Cars are categorized **by brand** (make == `category_id`); rentals use the rooms param
  (`parameters[69]`) + price in som; microdistricts are not a structured filter (matched in text).
- The HTTP client retries transient network/5xx errors and paces paginated requests.

## Carcheck (fines) — important

[Carcheck](https://carcheck.gov.kg) (by the State Registration Service) checks fines,
arrest/pledge status and history by plate, but it is gated by **login + Google reCAPTCHA**
— its backend returns `401` without a session — so it **cannot be automated**. `check_fines`
is therefore a *link assistant*: it normalizes the plate and returns the URLs; you complete
login + captcha. Note that license plates are **not** published in Lalafo listings, so get the
plate from the seller.

## Disclaimer

For personal and educational use. Respect the Terms of Service of Lalafo and Carcheck and
avoid aggressive request rates. Not affiliated with Lalafo or the State Registration Service.
