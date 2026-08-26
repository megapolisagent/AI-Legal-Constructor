"""Логика динамического комплекта — handoff §5, расширяемость — handoff §13.2.

Состав комплекта больше не зашит в этот код: он читается из document_rules.json
(рядом с этим skill), чтобы агент мог сам добавить новый тип документа (новую
запись в document_rules.json + шаблон в templates_docx/registry.json) без правки
Python. Этот файл — только интерпретатор трёх видов правил (per_participant,
once_per_deal, per_participant_flag), сам не решает, какие документы нужны."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from models import Deal, Participant

SKILL_ROOT = Path(__file__).resolve().parent.parent  # skills/document-assembly/
RULES_PATH = SKILL_ROOT / "document_rules.json"


@dataclass
class DocumentTask:
    document_type: str  # комиссия | основной_договор | акт | согласие | ... (расширяемо)
    participant: Participant | None  # None для документов на всю сделку
    consent_reason: str | None = None  # для per_participant_flag — какой флаг вызвал документ
    label: str = ""  # человеко-читаемое имя для имени файла


def _load_rules() -> list[dict]:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return data["rules"]


def _flag_value(p: Participant, flag: str) -> bool:
    """Ищет флаг сначала как поле Participant (is_married и т.п.), потом в extra_flags —
    новый триггер согласия можно завести через extra_flags, без правки models.py."""
    if hasattr(p, flag):
        return bool(getattr(p, flag))
    return bool(p.extra_flags.get(flag))


def build_document_set(deal: Deal) -> list[DocumentTask]:
    """Определяет итоговый список документов под конкретный состав участников (§5),
    исполняя правила из document_rules.json (§13.2) — не решает сама, что за правила."""
    tasks: list[DocumentTask] = []

    for rule in _load_rules():
        scope = rule["scope"]
        document_type = rule["document_type"]
        label_template = rule.get("label_template", document_type)

        if scope == "per_participant":
            for p in deal.participants:
                name = p.full_name or p.participant_id
                tasks.append(DocumentTask(
                    document_type=document_type,
                    participant=p,
                    label=label_template.format(full_name=name),
                ))

        elif scope == "once_per_deal":
            if deal.participants:
                tasks.append(DocumentTask(
                    document_type=document_type,
                    participant=None,
                    label=label_template.format(),
                ))

        elif scope == "per_participant_flag":
            flag = rule["flag"]
            flag_label = rule.get("flag_label", flag)
            for p in deal.participants:
                if not _flag_value(p, flag):
                    continue
                name = p.full_name or p.participant_id
                tasks.append(DocumentTask(
                    document_type=document_type,
                    participant=p,
                    consent_reason=flag,
                    label=label_template.format(flag_label=flag_label, full_name=name),
                ))

        else:
            raise ValueError(
                f"document_rules.json: неизвестный scope «{scope}» у правила {document_type} — "
                f"поддерживаются per_participant, once_per_deal, per_participant_flag"
            )

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
