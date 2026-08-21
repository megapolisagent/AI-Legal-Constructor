"""Реестр шаблонов — handoff §5. На пару (document_type × deal_type) только один active.
Перенесено без изменений логики из archive/web_proto/app/registry.py — путь пересчитан
под новое расположение (scripts/ теперь прямо в корне репозитория, не app/ на уровень глубже)."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "templates_docx" / "registry.json"
TEMPLATES_DIR = REGISTRY_PATH.parent


class TemplateNotFound(Exception):
    pass


def _load() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def active_template_path(document_type: str, deal_type: str) -> tuple[Path, str]:
    registry = _load()
    key = f"{document_type}__{deal_type}"
    entries = [e for e in registry["entries"] if e["key"] == key and e["status"] == "active"]
    if not entries:
        raise TemplateNotFound(
            f"Нет active-шаблона для {document_type} / {deal_type} — проверь templates_docx/registry.json"
        )
    if len(entries) > 1:
        raise TemplateNotFound(
            f"Больше одного active-шаблона для {document_type} / {deal_type} — нарушено правило §5 (registry)"
        )
    return TEMPLATES_DIR / entries[0]["file"], entries[0]["version"]


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python registry_lookup.py <document_type> <deal_type>", file=sys.stderr)
        sys.exit(2)
    try:
        path, version = active_template_path(sys.argv[1], sys.argv[2])
        print(f"{path} (версия {version})")
    except TemplateNotFound as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
