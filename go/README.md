# lalafo-mcp (Go)

Go port of the Lalafo search + Carcheck MCP server — a single static binary, no runtime.
Built on the official [Go MCP SDK](https://github.com/modelcontextprotocol/go-sdk).
See the [repository root README](../README.md) for the project overview and rationale.

## Tools

| Tool | Description |
|------|-------------|
| `check_fines(plate)` | Normalizes a KG plate and returns Carcheck links + mashina.kg / tolom.kg / balance.kg. Carcheck is gated by login + reCAPTCHA → the user completes login and the captcha. |
| `search(query, per_page, strict)` | Keyword search. `strict` (default `true`) drops irrelevant padding. |
| `search_cars(make, model, year_from, price_max_usd)` | Cars: brand → category, year → range, price normalized to USD. |
| `search_rentals(rooms, price_max, district, deal, exclude_shared)` | Apartment rentals: rooms, price in som, district by text, room-shares («подселение») filtered out. |

## Build & run

```bash
cd go
go mod tidy
go build -o lalafo-mcp.exe        # one static binary
./lalafo-mcp.exe                  # MCP server over stdio

go run . -selftest                # live smoke test (no MCP client)
```

Optionally copy `.env.example` → `.env` to set `LALAFO_COUNTRY_ID`
(12 = Kyrgyzstan), `LALAFO_LANGUAGE`, `USD_KGS_RATE`.

### Connect to Claude Code

```bash
claude mcp add lalafo-kg -- /ABS/PATH/lalafo-mcp/go/lalafo-mcp.exe
```

## Notes

- Same verified facts as the Python version: endpoint `api.lalafo.com/v3/ads/search` (no auth, but the mandatory `country-id` / `device` / `language` headers), `parameters[ID]=value_id` for select filters, `parameters[62][from]` (literal year) for a range, the currency-blind price filter → USD computed client-side, and the silently-ignored bad filter → the server verifies `totalCount` actually shrank.
- Carcheck cannot be automated (login + reCAPTCHA, backend `/api/violation-check/find-by-plate` → 401). License plates are not present in Lalafo listings.
- HTTP client: retries on transient network/5xx errors + 0.25 s pacing between paginated pages.

## Layout

```
client.go    # net/http + retry, Ad/SearchResponse types
carcheck.go  # plate normalization + links
core.go      # search_listings / search_cars / search_rentals + helpers
main.go      # mcp.AddTool ×4 + -selftest mode
```
