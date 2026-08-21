"""Модель данных Deal/Participants — раздел 4 handoff v1.1."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

DEAL_TYPES = ("аренда", "продажа")
SIDES = ("сторона объекта", "сторона контрагента")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class Participant:
    participant_id: str
    side: str  # "сторона объекта" | "сторона контрагента"
    full_name: str = ""
    passport_data: str = ""
    registration_address: str = ""
    contact: str = ""
    representative: str = ""  # доверенность, если действует не сам
    ownership_share: str = ""  # доля в праве (для стороны объекта, если долевая)
    is_married: bool = False
    is_minor: bool = False
    has_other_co_owners: bool = False
    commission_value: str = ""  # % или сумма, может отличаться по участнику

    @staticmethod
    def create(side: str) -> "Participant":
        return Participant(participant_id=new_id("p"), side=side)


@dataclass
class Deal:
    deal_id: str
    deal_type: str = "аренда"
    status: str = "draft"
    agent_id: str = "maria"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Object
    address: str = ""
    cadastral_number: str = ""
    property_type: str = ""
    area: str = ""
    rooms: str = ""
    ownership_basis: str = ""
    encumbrances: str = ""

    # Participants
    participants: list[Participant] = field(default_factory=list)

    # Deal Terms
    price: str = ""
    payment_schedule: str = ""
    deposit: str = ""
    term: str = ""
    special_conditions: str = ""

    # Agency details (commission terms, shared part)
    agency_name: str = "Мегаполис"
    agency_inn: str = ""
    agency_ogrn: str = ""
    agency_signatory: str = ""

    @staticmethod
    def create(deal_type: str) -> "Deal":
        return Deal(deal_id=new_id("deal"), deal_type=deal_type)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Deal":
        participants = [Participant(**p) for p in data.pop("participants", [])]
        deal = Deal(**data)
        deal.participants = participants
        return deal
