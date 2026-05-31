"""FastMCP server — thin tool wrappers over carcheck + core."""
from mcp.server.fastmcp import FastMCP

from . import carcheck, core, subscriptions

mcp = FastMCP("lalafo-kg")


@mcp.tool()
def check_fines(plate: str) -> dict:
    """Проверка штрафов/истории авто по госномеру (Кыргызстан) через Carcheck.

    Carcheck — госсервис с логином и reCAPTCHA, поэтому автопроверка невозможна.
    Инструмент нормализует номер и возвращает готовые ссылки; вход и капчу проходит
    пользователь. Госномер в объявлениях Lalafo не публикуется — берите его у продавца.
    """
    plate_norm = carcheck.normalize_plate(plate)
    return {
        "plate_input": plate,
        "plate_normalized": plate_norm,
        "valid_format": carcheck.is_plausible_plate(plate_norm),
        "links": carcheck.build_links(plate_norm),
        "note": carcheck.NOTE,
    }


@mcp.tool()
def search(query: str, per_page: int = 30, strict: bool = True) -> list:
    """Поиск объявлений на Lalafo по ключевым словам.

    Поиск Lalafo — «recall over precision»: при strict=True отбрасываем нерелевантную
    «мешанину» (все токены запроса должны встречаться в названии/описании) и сортируем
    по релевантности, а не по дате/промо.
    """
    return core.search_listings(query, per_page, strict)


@mcp.tool()
def search_cars(make: str, model: str = "", year_from: int = 0,
                price_max_usd: int = 0, per_page: int = 50) -> dict:
    """Поиск авто на Lalafo с учётом особенностей API.

    make — марка (определяет категорию), model — модель (матч по названию),
    year_from — год «от» (диапазон), price_max_usd — потолок цены в долларах
    (цена нормализуется в USD, т.к. серверный фильтр цены слеп к валюте).
    """
    return core.search_cars(make, model, year_from or None, price_max_usd or None, per_page)


@mcp.tool()
def search_rentals(rooms: str = "", price_max: int = 0, district: str = "",
                   deal: str = "long", exclude_shared: bool = True, per_page: int = 50) -> dict:
    """Поиск аренды квартир на Lalafo (Бишкек/КР).

    rooms — '1'..'4' или 'студия' (пусто = любое); price_max — потолок в СОМАХ;
    district — район/микрорайон текстом (напр. '7 микрорайон'): фильтр клиентский, т.к.
    структурного параметра района у Lalafo нет; deal — 'long' (долгосрочно) или 'daily'
    (посуточно); exclude_shared=True убирает «подселение» (комната в квартире, не вся).
    """
    return core.search_rentals(rooms, price_max, district, deal, exclude_shared, per_page)


@mcp.tool()
def subscribe(name: str, kind: str, query: str = "", rooms: str = "", price_max: int = 0,
              district: str = "", deal: str = "long", make: str = "", model: str = "",
              year_from: int = 0, price_max_usd: int = 0) -> dict:
    """Подписаться на поиск и отслеживать НОВЫЕ подходящие объявления.

    kind: 'search' (заполни query), 'cars' (make/model/year_from/price_max_usd) или
    'rentals' (rooms/price_max/district/deal). Существующие объявления при создании
    помечаются как «уже виденные» — уведомления придут только о новых.
    Уведомления уходят в каналы из env (ntfy/Telegram/webhook), если настроены.
    """
    if kind == "search":
        params = {"query": query}
    elif kind == "cars":
        params = {"make": make, "model": model, "year_from": year_from, "price_max_usd": price_max_usd}
    elif kind == "rentals":
        params = {"rooms": rooms, "price_max": price_max, "district": district, "deal": deal}
    else:
        return {"error": "kind должен быть: search | cars | rentals"}
    return subscriptions.add(name, kind, params)


@mcp.tool()
def list_subscriptions() -> list:
    """Список сохранённых подписок на поиск."""
    return subscriptions.list_all()


@mcp.tool()
def unsubscribe(subscription_id: str) -> dict:
    """Удалить подписку по id."""
    return subscriptions.remove(subscription_id)


@mcp.tool()
def check_subscriptions(subscription_id: str = "") -> dict:
    """Проверить подписки и вернуть объявления, появившиеся с прошлой проверки.

    Без аргумента проверяет все подписки. Если настроены каналы уведомлений
    (ntfy/Telegram/webhook) — отправляет их. Подходит для запуска по расписанию/в /loop.
    """
    return subscriptions.check(subscription_id or None, notify_channels=True)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
