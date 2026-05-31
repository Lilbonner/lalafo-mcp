# lalafo-mcp

MCP-сервер для Кыргызстана: поиск объявлений на **Lalafo** и ассистент проверки штрафов через **Carcheck**.

## Инструменты

| Tool | Что делает |
|------|------------|
| `check_fines(plate)` | Нормализует госномер и отдаёт ссылки на Carcheck (офиц.) + mashina.kg / tolom.kg / balance.kg. Carcheck закрыт логином и reCAPTCHA, поэтому это ассистент — вход и капчу проходит пользователь. |
| `search(query, per_page, strict)` | Поиск по ключевым словам. `strict=True` убирает нерелевантную «мешанину» (Lalafo оптимизирует recall, а не точность) и сортирует по релевантности. |
| `search_cars(make, model, year_from, price_max_usd)` | Поиск авто. Учитывает 3 особенности API: марка = категория, год = числовой диапазон, а цену в USD считает сам (серверный фильтр цены слеп к валюте). |

## Запуск

Нужен Python 3.10+. Рекомендуется [uv](https://docs.astral.sh/uv/).

```bash
cd C:\projects\lalafo-mcp
uv sync                 # или: pip install -e .
uv run lalafo-mcp       # запуск MCP-сервера (stdio)
```

Перед стартом можно скопировать `.env.example` → `.env` и задать `LALAFO_COUNTRY_ID`
(12 = Кыргызстан), `LALAFO_LANGUAGE`, `USD_KGS_RATE`.

### Подключение к Claude Code

```bash
claude mcp add lalafo-kg -- uv run --directory C:\projects\lalafo-mcp lalafo-mcp
```

(Без uv: `pip install -e .`, затем команда `lalafo-mcp` или `python -m lalafo_mcp.server`.)

## Проверка логики без MCP

```bash
python selftest.py      # бьёт по живому API: check_fines + search + search_cars
```

## Заметки / ограничения

- **Carcheck нельзя автоматизировать**: госсервис с логином + reCAPTCHA (бэкенд `/api/violation-check/find-by-plate` → 401 без сессии). Инструмент только готовит ссылку и нормализует номер.
- **Госномер в объявлениях Lalafo не публикуется** — для `check_fines` берите номер у продавца / с фото.
- **Цена авто нормализуется в USD на клиенте** — серверный `price[to]` сравнивает голое число, мешая $ и сом. Курс задаётся `USD_KGS_RATE`.
- **Тихий игнор фильтров**: Lalafo молча отбрасывает невалидный фильтр (не ошибка). `search_cars` проверяет, что фильтр по году реально сузил выдачу, и иначе возвращает `warning`.
- Использовать в рамках ToS площадок; без агрессивных частот запросов.

## Структура

```
src/lalafo_mcp/
  client.py     # Lalafo API (stdlib urllib): /v3/ads/search, /v3/ads/{id}
  core.py       # логика: search_listings, search_cars (mcp-free, тестируемо)
  carcheck.py   # нормализация госномера + генерация ссылок
  server.py     # FastMCP-обёртки (check_fines, search, search_cars)
```

Дальше можно добавить `search_rentals` (категории 2043/2044, комнаты `parameters[69]`, цена
`price[from]/[to]`, текст-фильтр по микрорайону, стоп-слова «подселение»).
