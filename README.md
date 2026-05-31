# lalafo-mcp

MCP-сервер для Кыргызстана: поиск объявлений на **Lalafo** + ассистент проверки штрафов **Carcheck**.
Две независимые реализации одного набора инструментов:

| | Каталог | Стек | Запуск |
|---|---|---|---|
| **Python** | [`python/`](python/) | FastMCP | `uv run lalafo-mcp` |
| **Go** | [`go/`](go/) | официальный Go MCP SDK | `go build` → один `.exe` |

## Инструменты

| Tool | Что делает |
|------|------------|
| `check_fines(plate)` | Нормализует госномер и отдаёт ссылки на Carcheck (офиц.) + mashina.kg / tolom.kg / balance.kg. Carcheck закрыт логином и reCAPTCHA → вход/капчу проходит пользователь. |
| `search(query, …)` | Поиск по словам; `strict` убирает нерелевантную «мешанину». |
| `search_cars(make, model, year_from, price_max_usd)` | Авто: марка→категория, год→диапазон, цена нормализуется в USD. |
| `search_rentals(rooms, price_max, district, deal)` | Аренда квартир: комнаты, цена в сомах, район текстом, отсев «подселения». |

## Особенности Lalafo API (учтены в обеих версиях)

- Endpoint `api.lalafo.com/v3/ads/search` — без авторизации, но с обязательными заголовками `country-id` / `device` / `language`.
- Select-параметры: `parameters[<id>]=<value_id>`; числовой диапазон (год): `parameters[62][from]=<год>`.
- Фильтр цены **слеп к валюте** → цена авто нормализуется в USD на клиенте.
- Кривой/неизвестный фильтр Lalafo **молча игнорирует** → проверяем, что `totalCount` сузился.
- Carcheck автоматизировать нельзя (логин + reCAPTCHA); госномера в объявлениях Lalafo нет.

Подробности и инструкции — в README внутри `python/` и `go/`.
