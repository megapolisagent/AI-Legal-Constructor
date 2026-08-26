"""Filesystem-first хранение Deal — как source of truth (handoff §8, Phase 1: без БД)."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Deal

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "deals"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def save(deal: Deal) -> None:
    path = DATA_DIR / f"{deal.deal_id}.json"
    path.write_text(json.dumps(deal.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load(deal_id: str) -> Deal | None:
    path = DATA_DIR / f"{deal_id}.json"
    if not path.exists():
        return None
    return Deal.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_deals() -> list[Deal]:
    deals = [Deal.from_dict(json.loads(p.read_text(encoding="utf-8"))) for p in DATA_DIR.glob("*.json")]
    deals.sort(key=lambda d: d.created_at, reverse=True)
    return deals
