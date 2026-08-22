"""Инструмент агента: собрать комплект .docx по данным сделки (handoff §5, §7).
Перенесено без изменений логики рендеринга из archive/web_proto/app/generator.py —
изменился только путь вывода (output/<deal_id>/ в корне репозитория, не generated/
внутри Flask-приложения) и то, что вызывается как CLI, а не из веб-маршрута.

Использование (из корня репозитория): python skills/document-assembly/scripts/generate_package.py deals/<deal_id>/deal.json

Не генерирует, если есть незаполненные поля — сначала прогони check_completeness.py
и закрой пробелы (или явно реши с пользователем, что часть документов откладывается)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docxtpl import DocxTemplate

from models import Deal, load_deal
from registry_lookup import active_template_path, TemplateNotFound
from rules import build_document_set, missing_fields, DocumentTask

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # .../scripts/../../../ → repo root
OUTPUT_DIR = REPO_ROOT / "output"


def _safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()[:120]


def _context_for_task(deal: Deal, task: DocumentTask) -> dict:
    ctx = {
        "deal_id": deal.deal_id,
        "deal_type": deal.deal_type,
        "address": deal.address,
        "cadastral_number": deal.cadastral_number,
        "property_type": deal.property_type,
        "area": deal.area,
        "rooms": deal.rooms,
        "ownership_basis": deal.ownership_basis,
        "encumbrances": deal.encumbrances,
        "price": deal.price,
        "payment_schedule": deal.payment_schedule,
        "deposit": deal.deposit,
        "term": deal.term,
        "special_conditions": deal.special_conditions,
        "agency_name": deal.agency_name,
        "agency_inn": deal.agency_inn,
        "agency_ogrn": deal.agency_ogrn,
        "agency_signatory": deal.agency_signatory,
        "participants": [p.__dict__ for p in deal.participants],
        "object_side": [p.__dict__ for p in deal.participants if p.side == "сторона объекта"],
        "counterparty_side": [p.__dict__ for p in deal.participants if p.side == "сторона контрагента"],
    }
    if task.participant is not None:
        ctx["participant"] = task.participant.__dict__
        ctx["commission_value"] = task.participant.commission_value
    if task.consent_reason is not None:
        ctx["consent_reason"] = task.consent_reason
    return ctx


def generate_package(deal: Deal) -> tuple[list[dict], list[dict]]:
    """Возвращает (успешно сгенерированные файлы, ошибки шаблонов) — не бросает исключение
    на отсутствующий шаблон, чтобы агент показал список проблем целиком (§5, шаг 3)."""
    out_dir = OUTPUT_DIR / deal.deal_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = build_document_set(deal)
    files: list[dict] = []
    errors: list[dict] = []
    used_names: set[str] = set()

    for task in tasks:
        try:
            template_path, version = active_template_path(task.document_type, deal.deal_type)
        except TemplateNotFound as exc:
            errors.append({"label": task.label, "reason": str(exc)})
            continue

        doc = DocxTemplate(str(template_path))
        doc.render(_context_for_task(deal, task))

        base_name = _safe_filename(task.label) or task.document_type
        filename = f"{base_name}.docx"
        n = 2
        while filename in used_names:
            filename = f"{base_name} ({n}).docx"
            n += 1
        used_names.add(filename)

        out_path = out_dir / filename
        doc.save(str(out_path))
        files.append({
            "label": task.label,
            "filename": filename,
            "document_type": task.document_type,
            "template_version": version,
        })

    return files, errors


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python generate_package.py <путь к deal.json>", file=sys.stderr)
        sys.exit(2)

    deal = load_deal(sys.argv[1])

    problems = missing_fields(deal)
    if problems:
        print("Не хватает данных — сначала прогони check_completeness.py:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    files, errors = generate_package(deal)

    out_dir = OUTPUT_DIR / deal.deal_id
    print(f"Собрано {len(files)} документов в {out_dir}:")
    for f in files:
        print(f"  - {f['filename']} ({f['document_type']}, шаблон {f['template_version']})")

    if errors:
        print("\nОшибки шаблонов:", file=sys.stderr)
        for e in errors:
            print(f"  - {e['label']}: {e['reason']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
