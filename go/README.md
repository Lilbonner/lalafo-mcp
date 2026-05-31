# lalafo-mcp-go

Go-порт MCP-сервера для Кыргызстана: поиск объявлений **Lalafo** + ассистент проверки штрафов **Carcheck**.
Один статический бинарник, без рантайма. Официальный [Go MCP SDK](https://github.com/modelcontextprotocol/go-sdk).

## Инструменты

| Tool | Что делает |
|------|------------|
| `check_fines(plate)` | Нормализует госномер и отдаёт ссылки на Carcheck + mashina.kg/tolom.kg/balance.kg. Carcheck закрыт логином + reCAPTCHA → вход/капчу проходит пользователь. |
| `search(query, per_page, strict)` | Поиск по словам. `strict` (по умолч. true) убирает нерелевантную «мешанину». |
| `search_cars(make, model, year_from, price_max_usd)` | Авто: марка→категория, год→диапазон, цена нормализуется в USD. |
| `search_rentals(rooms, price_max, district, deal, exclude_shared)` | Аренда квартир: комнаты, цена в сомах, район текстом, отсев «подселения». |

## Сборка и запуск

```bash
cd C:\projects\lalafo-mcp-go
go mod tidy
go build -o lalafo-mcp.exe        # один бинарник
.\lalafo-mcp.exe                  # MCP-сервер по stdio

go run . -selftest                # живой прогон логики (без MCP)
```

### Подключение к Claude Code

```bash
claude mcp add lalafo-kg -- C:\projects\lalafo-mcp-go\lalafo-mcp.exe
```

## Заметки

- Те же проверенные факты, что и в Python-версии: endpoint `api.lalafo.com/v3/ads/search` (без auth, но с обяз. заголовками `country-id/device/language`), `parameters[ID]=value_id` для select-параметров, `parameters[62][from]` (литерал года) для диапазона, фильтр цены слеп к валюте → USD считаем сами, кривой фильтр Lalafo **молча игнорирует** → проверяем, что totalCount сузился.
- Carcheck автоматизировать нельзя (логин + reCAPTCHA, бэкенд `/api/violation-check/find-by-plate` → 401). Госномера в объявлениях Lalafo нет.
- Клиент: ретраи на транзиентных сетевых/5xx ошибках + пауза 0.25с между страницами.

## Структура

```
client.go    # net/http + retry, типы Ad/SearchResponse
carcheck.go  # нормализация номера + ссылки
core.go      # search_listings / search_cars / search_rentals + хелперы
main.go      # mcp.AddTool ×4 + режим -selftest
```
