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
from rules import (
    build_document_set,
    missing_fields,
    DocumentTask,
    REQUIRED_DEAL_FIELDS,
    REQUIRED_PARTICIPANT_FIELDS,
)

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


class ContextValidationError(ValueError):
    """Контекст для render() неполон по обязательным полям. Не то же самое, что
    missing_fields() в main(): та проверка не сработает, если generate_package() вызван не
    через CLI — эта проверка стоит прямо перед render(), защита не зависит от вызывающего кода."""


def _validate_context(ctx: dict, label: str) -> None:
    """Проверяет только обязательные реквизиты (тот же список, что и missing_fields() —
    REQUIRED_DEAL_FIELDS/REQUIRED_PARTICIPANT_FIELDS из rules.py), не любое пустое поле:
    у многих полей (special_conditions, encumbrances, deposit) легитимно пустое значение
    означает «нет условия», не «данные потерялись» — блокировать их было бы ложной тревогой,
    не защитой."""
    missing = []
    for field_name in REQUIRED_DEAL_FIELDS:
        if not ctx.get(field_name):
            missing.append(f"deal.{field_name}")

    for group_key in ("participants",):
        for i, p in enumerate(ctx.get(group_key) or []):
            for field_name in REQUIRED_PARTICIPANT_FIELDS:
                if not p.get(field_name):
                    missing.append(f"{group_key}[{i}].{field_name}")

    if missing:
        raise ContextValidationError(
            f"Документ «{label}»: обязательные реквизиты не заполнены — {', '.join(missing)}. "
            "Не рендерю с пропуском — подставленное пустое значение в готовом договоре опаснее "
            "явной остановки."
        )


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

        ctx = _context_for_task(deal, task)
        _validate_context(ctx, task.label)

        doc = DocxTemplate(str(template_path))
        doc.render(ctx)

        base_name = _safe_filename(task.label) or task.document_type
        filename = f"{base_name}.docx"
        n = 2
        while filename in used_names:
            filename = f"{base_name} ({n}).docx"
            n += 1
        used_names.add(filename)

        out_path = out_dir / filename
        doc.save(str(out_path))

        pdf_filename = _convert_to_pdf(out_path)

        files.append({
            "label": task.label,
            "filename": filename,
            "pdf_filename": pdf_filename,
            "document_type": task.document_type,
            "template_version": version,
        })

    return files, errors


def _convert_to_pdf(docx_path: Path) -> str | None:
    """Готовый PDF рядом с .docx — финальный подписываемый артефакт, .docx остаётся
    редактируемым рабочим файлом. Не через LibreOffice (не установлен на этой машине,
    проверено 2026-09-03) — через docx2pdf (COM-автоматизация реально установленного MS
    Word, `Program Files/Microsoft Office/root/Office16/WINWORD.EXE`, подтверждено прямым
    прогоном). На машине без Word/pywin32 — не роняет всю генерацию: пропускает PDF-шаг,
    .docx всё равно готов, явно сообщает об этом в stderr, не молчит."""
    try:
        from docx2pdf import convert
    except ImportError:
        print(
            f"  [PDF] docx2pdf/pywin32 не установлены — «{docx_path.name}» остался только .docx.",
            file=sys.stderr,
        )
        return None

    pdf_path = docx_path.with_suffix(".pdf")
    try:
        convert(str(docx_path), str(pdf_path))
    except Exception as exc:  # COM-ошибка/нет Word на этой машине — не роняем всю генерацию
        print(f"  [PDF] Не удалось собрать PDF для «{docx_path.name}»: {exc}", file=sys.stderr)
        return None
    return pdf_path.name


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
        pdf_note = f", PDF: {f['pdf_filename']}" if f.get("pdf_filename") else ", PDF: не собран"
        print(f"  - {f['filename']} ({f['document_type']}, шаблон {f['template_version']}){pdf_note}")

    if errors:
        print("\nОшибки шаблонов:", file=sys.stderr)
        for e in errors:
            print(f"  - {e['label']}: {e['reason']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
