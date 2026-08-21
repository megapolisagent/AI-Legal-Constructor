"""Логика динамического комплекта — handoff §5. Комплект не фиксирован (не 3 документа)."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Deal, Participant

CONSENT_LABELS = {
    "is_married": "Согласие супруга",
    "is_minor": "Согласие органа опеки",
    "has_other_co_owners": "Согласие содольщика",
}


@dataclass
class DocumentTask:
    document_type: str  # комиссия | основной_договор | акт | согласие
    participant: Participant | None  # None для документов на всю сделку
    consent_reason: str | None = None  # для согласия — какой флаг его вызвал
    label: str = ""  # человеко-читаемое имя для UI/имени файла


def build_document_set(deal: Deal) -> list[DocumentTask]:
    """Определяет итоговый список документов под конкретный состав участников (§5)."""
    tasks: list[DocumentTask] = []

    for p in deal.participants:
        tasks.append(DocumentTask(
            document_type="комиссия",
            participant=p,
            label=f"Комиссия — {p.full_name or p.participant_id}",
        ))

    if deal.participants:
        tasks.append(DocumentTask(
            document_type="основной_договор",
            participant=None,
            label="Основной договор",
        ))
        tasks.append(DocumentTask(
            document_type="акт",
            participant=None,
            label="Акт приёма-передачи",
        ))

    for p in deal.participants:
        for flag_field, label in CONSENT_LABELS.items():
            if getattr(p, flag_field):
                tasks.append(DocumentTask(
                    document_type="согласие",
                    participant=p,
                    consent_reason=flag_field,
                    label=f"{label} — {p.full_name or p.participant_id}",
                ))

    return tasks


REQUIRED_DEAL_FIELDS = ["address", "cadastral_number", "price"]
REQUIRED_PARTICIPANT_FIELDS = ["full_name", "passport_data"]


def missing_fields(deal: Deal) -> list[str]:
    """Проверка полноты данных под определённый комплект — §5 «поток генерации», шаг 3."""
    missing: list[str] = []

    for field_name in REQUIRED_DEAL_FIELDS:
        if not getattr(deal, field_name):
            missing.append(f"Сделка: поле «{field_name}» не заполнено")

    if not deal.participants:
        missing.append("Сделка: нет ни одного участника")

    for p in deal.participants:
        for field_name in REQUIRED_PARTICIPANT_FIELDS:
            if not getattr(p, field_name):
                missing.append(f"Участник {p.full_name or p.participant_id}: поле «{field_name}» не заполнено")
        if p.side == "сторона объекта" and not p.ownership_share and len(
            [x for x in deal.participants if x.side == "сторона объекта"]
        ) > 1:
            missing.append(f"Участник {p.full_name or p.participant_id}: несколько собственников — нужна доля (ownership_share)")

    return missing
