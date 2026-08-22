"""Инструмент агента: проверка полноты данных сделки перед сборкой (handoff §5, шаг 3).

Использование (из корня репозитория): python skills/document-assembly/scripts/check_completeness.py deals/<deal_id>/deal.json

Печатает: итоговый список документов комплекта под текущий состав участников,
и — если есть — список незаполненных полей. Не генерирует файлы, только проверяет.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import load_deal
from rules import build_document_set, missing_fields


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python check_completeness.py <путь к deal.json>", file=sys.stderr)
        sys.exit(2)

    deal = load_deal(sys.argv[1])
    tasks = build_document_set(deal)
    problems = missing_fields(deal)

    print(f"Сделка {deal.deal_id} ({deal.deal_type}) — комплект из {len(tasks)} документов:")
    for t in tasks:
        print(f"  - {t.label} [{t.document_type}]")

    if problems:
        print("\nНе хватает данных:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    else:
        print("\nДанных достаточно — можно собирать (generate_package.py).")


if __name__ == "__main__":
    main()
