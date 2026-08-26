"""Сквозной тест движка: 2 собственника (один в браке, доли) + 1 покупатель =
ожидается 3 комиссии + 1 основной договор + 1 акт + 1 согласие супруга = 6 файлов
(тот же пример, что в handoff §5)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Deal, Participant
from app.rules import build_document_set, missing_fields
from app.generator import generate_package

deal = Deal.create(deal_type="продажа")
deal.address = "Москва, ул. Тестовая, д. 1, кв. 2"
deal.cadastral_number = "77:01:0001001:1234"
deal.price = "35 000 000 руб."

owner1 = Participant.create(side="сторона объекта")
owner1.full_name = "Иванова Ирина Ивановна"
owner1.passport_data = "0000 000000"
owner1.ownership_share = "1/2"
owner1.is_married = True

owner2 = Participant.create(side="сторона объекта")
owner2.full_name = "Иванов Пётр Иванович"
owner2.passport_data = "1111 111111"
owner2.ownership_share = "1/2"

buyer = Participant.create(side="сторона контрагента")
buyer.full_name = "Петров Иван Петрович"
buyer.passport_data = "2222 222222"

deal.participants = [owner1, owner2, buyer]

problems = missing_fields(deal)
assert not problems, f"Не должно быть незаполненных полей: {problems}"

tasks = build_document_set(deal)
print(f"Документов в комплекте: {len(tasks)}")
for t in tasks:
    print(" -", t.label, f"[{t.document_type}]")

assert len(tasks) == 6, f"Ожидалось 6 документов (пример из §5), получили {len(tasks)}"

files, errors = generate_package(deal)
print(f"\nСгенерировано файлов: {len(files)}, ошибок шаблонов: {len(errors)}")
for f in files:
    print(" ->", f["filename"])
for e in errors:
    print(" !! ОШИБКА:", e)

assert not errors, f"Не должно быть ошибок шаблонов: {errors}"
assert len(files) == 6

out_dir = Path(__file__).resolve().parent.parent / "generated" / deal.deal_id
for f in files:
    p = out_dir / f["filename"]
    assert p.exists() and p.stat().st_size > 0, f"Файл не создан или пустой: {p}"

print("\nSMOKE TEST: OK — движок собирает комплект end-to-end без ошибок.")
