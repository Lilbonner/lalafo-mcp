"""Carcheck (KG traffic-fine / vehicle-history) link assistant.

Carcheck (carcheck.gov.kg, by ГРС / ГП «Унаа») is a government service gated by
LOGIN + Google reCAPTCHA — its backend (/api/violation-check/find-by-plate) returns
401 without an authenticated session. So we cannot auto-query it. Instead we normalize
the plate and hand back ready-to-open links; the user completes login + captcha.
"""
import re

NOTE = (
    "Carcheck — госсервис с входом и reCAPTCHA, автоматическая проверка невозможна. "
    "Откройте ссылку, при необходимости вставьте госномер и пройдите капчу. "
    "Проверяются только номера, выданные в КР (формат вроде 01KG555BRQ)."
)

# Official service first, then well-known third-party checkers (same underlying data).
_SERVICES = [
    ("carcheck.gov.kg — официальный (ГРС)", "https://carcheck.gov.kg/ru"),
    ("mashina.kg — история по госномеру", "https://m.mashina.kg/carcheck/"),
    ("tolom.kg — проверка штрафов", "https://tolom.kg/"),
    ("balance.kg — проверка/оплата штрафов", "https://balance.kg/"),
]

# Lenient KG plate shape after normalization, e.g. 01KG555BRQ (digits + Latin/Cyrillic, 6-12).
_PLATE_RE = re.compile(r"^[0-9A-ZА-Я]{6,12}$")


def normalize_plate(raw: str) -> str:
    """'01 kg 555 brq' / '01-KG-555-BRQ' -> '01KG555BRQ'."""
    return re.sub(r"[^0-9A-Za-zА-Яа-я]", "", raw or "").upper()


def is_plausible_plate(plate: str) -> bool:
    return bool(_PLATE_RE.match(plate))


def build_links(plate: str) -> list[dict]:
    links = []
    for name, url in _SERVICES:
        # carcheck.gov.kg may read ?number=; prefill is not guaranteed — paste if empty.
        full = f"{url}?number={plate}" if plate and "carcheck.gov.kg" in url else url
        links.append({"service": name, "url": full})
    return links
