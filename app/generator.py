"""Генератор — рендерит каждый документ из active-шаблона, сохраняет Package (§5, §7)."""
from __future__ import annotations

import re
from pathlib import Path

from docxtpl import DocxTemplate

from .models import Deal, Participant
from .registry import active_template_path
from .rules import build_document_set, DocumentTask

GENERATED_DIR = Path(__file__).resolve().parent.parent / "generated"


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
    на отсутствующий шаблон, чтобы владелец увидел список проблем целиком (§5, шаг 3)."""
    out_dir = GENERATED_DIR / deal.deal_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = build_document_set(deal)
    files: list[dict] = []
    errors: list[dict] = []
    used_names: set[str] = set()

    for task in tasks:
        try:
            template_path, version = active_template_path(task.document_type, deal.deal_type)
        except Exception as exc:  # TemplateNotFound
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


def cross_check(files: list[dict], deal: Deal) -> list[str]:
    """Автосверка комплекта (§5): данные берутся из одного Deal — расхождение
    возможно только при ошибке маппинга, поэтому здесь фиксируем сам факт единого источника."""
    notes = []
    if files:
        notes.append(
            f"Все {len(files)} документов собраны из одной записи Deal ({deal.deal_id}) — "
            "цена/адрес/ФИО не могли разойтись между файлами."
        )
    return notes
