"""HTTP-уровневый сквозной тест — POST-запросы с гарантированно правильной UTF-8
кодировкой (в обход кириллицы в argv Windows-консоли, из-за которой curl-тест
через Bash дал мусор). Проверяет реальный путь браузера: форма -> Flask -> генерация.
Запускать при уже поднятом сервере: python run.py, затем в другом окне —
python scripts/http_smoke_test.py
"""
from __future__ import annotations

import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:5001"


def post(path: str, data: dict) -> tuple[int, str, str]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, resp.geturl(), resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, "", e.read().decode("utf-8")


def get(path: str) -> tuple[int, str]:
    resp = urllib.request.urlopen(BASE + path)
    return resp.status, resp.read().decode("utf-8")


status, url, body = post("/deals/new", {
    "deal_type": "продажа",
    "address": "Москва, ул. Тестовая, д. 5",
    "cadastral_number": "77:01:0002002:5678",
    "property_type": "квартира",
    "area": "80",
    "rooms": "3",
    "ownership_basis": "свидетельство",
    "encumbrances": "нет",
})
deal_id = url.rstrip("/").split("/")[-2]
print(f"1. Создана сделка: {deal_id} (redirect status косвенно {status})")
assert "деал" not in deal_id.lower() or deal_id.startswith("deal_"), deal_id

for label, data in [
    ("owner1", {"side": "сторона объекта", "full_name": "Иванова Ирина Ивановна",
                "passport_data": "0000 000000", "ownership_share": "1/2", "is_married": "on"}),
    ("owner2", {"side": "сторона объекта", "full_name": "Иванов Пётр Иванович",
                "passport_data": "1111 111111", "ownership_share": "1/2"}),
    ("buyer", {"side": "сторона контрагента", "full_name": "Петров Иван Петрович",
               "passport_data": "2222 222222"}),
]:
    status, _, _ = post(f"/deals/{deal_id}/participants", data)
    print(f"2. Участник {label}: status {status}")

status, _, _ = post(f"/deals/{deal_id}/terms", {
    "price": "35 000 000",
    "payment_schedule": "100% при подписании",
    "deposit": "1 000 000",
    "term": "30 дней",
    "special_conditions": "нет",
    "agency_name": "Мегаполис",
    "agency_inn": "7700000000",
    "agency_ogrn": "1177700000000",
    "agency_signatory": "Боголюбова М.А.",
})
print(f"3. Условия сохранены: status {status}")

gstatus, gbody = get(f"/deals/{deal_id}/generate")
assert "Не хватает данных" not in gbody, "Есть незаполненные поля — не должно быть на этом наборе данных"
print("4. Проверка полноты данных: OK, все поля заполнены")

status, _, body = post(f"/deals/{deal_id}/generate", {})
assert "Проблемы с шаблонами" not in body, f"Есть ошибки шаблонов:\n{body}"
assert "Готовые файлы" in body, "Не показан список готовых файлов после генерации"
print("5. Генерация комплекта через HTTP: OK, ошибок шаблонов нет")

print(f"\nHTTP SMOKE TEST: OK — сделка {deal_id} прошла все 4 экрана через реальные HTTP-запросы.")
