"""Live self-test of the mcp-free logic (stdlib only, hits the real Lalafo API).

Run:  python selftest.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ.setdefault("LALAFO_COUNTRY_ID", "12")

from lalafo_mcp import carcheck, core  # noqa: E402


def test_carcheck():
    print("== check_fines ==")
    p = carcheck.normalize_plate("01 kg 555 brq")
    assert p == "01KG555BRQ", p
    assert carcheck.is_plausible_plate(p)
    links = carcheck.build_links(p)
    assert any("carcheck.gov.kg" in l["url"] for l in links)
    for l in links:
        print(" ", l["service"], "->", l["url"])
    print("  normalized:", p, "| valid:", carcheck.is_plausible_plate(p))


def test_search():
    print("\n== search('koss porta', strict) ==")
    res = core.search_listings("koss porta", per_page=40, strict=True)
    print(f"  strict-filtered hits: {len(res)}")
    for r in res[:5]:
        print(f"   {r['price']} {r['currency']} | {r['title'][:45]} | rel={r['relevance']}")


def test_cars():
    print("\n== search_cars(Dodge Ram, >=2020, <=$30000) ==")
    res = core.search_cars("Dodge", model="Ram", year_from=2020, price_max_usd=30000)
    print(f"  category_id={res.get('category_id')} count={res.get('count')} warn={res.get('warning')}")
    for it in res.get("items", []):
        print(f"   ${it['price_usd']} ({it['price_raw']}) {it['year']} | {it['title'][:40]}")
        print(f"      {it['url']}")


def test_rentals():
    print("\n== search_rentals(2-комн, <=40000 сом, 7 микрорайон) ==")
    res = core.search_rentals(rooms="2", price_max=40000, district="7 микрорайон", deal="long")
    print(f"  server-total(2-комн<=40k)={res.get('total_matching_server_filters')} "
          f"scanned={res.get('scanned')} matched-district={res.get('count')} warn={res.get('warning')}")
    for it in res.get("items", []):
        print(f"   {it['price']} {it['currency']} | {it['title'][:42]} | {it['url']}")

    print("\n== search_rentals(студия, <=20000 сом, без района) — проверка фильтров ==")
    res2 = core.search_rentals(rooms="студия", price_max=20000)
    print(f"  server-total={res2.get('total_matching_server_filters')} sample={res2.get('count')}")
    for it in res2.get("items", [])[:3]:
        print(f"   {it['price']} {it['currency']} | {it['title'][:42]}")


if __name__ == "__main__":
    test_carcheck()
    test_search()
    test_cars()
    test_rentals()
    print("\nOK")
