"""OCR — локальное распознавание фото паспорта/ЕГРН через Tesseract (Phase 1.1).
Данные не покидают компьютер — тот же принцип, что и весь Вариант A (см. брифинг
2026-08-21). Точность распознавания ограничена и не гарантируется: все извлечённые поля
обязательно проходят экран проверки/правки, прежде чем попасть в Deal (main.py) —
это прямое требование владельца, не техническая деталь."""
from __future__ import annotations

import io
import os
import re
import shutil
from pathlib import Path

import pytesseract
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_TESSDATA = REPO_ROOT / "tessdata"

_TESSERACT_CANDIDATES = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
]


def _find_tesseract() -> Path | None:
    found = shutil.which("tesseract")
    if found:
        return Path(found)
    for candidate in _TESSERACT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def is_available() -> tuple[bool, str]:
    """(доступен ли OCR, причина если нет) — для честного сообщения в UI вместо падения."""
    exe = _find_tesseract()
    if exe is None:
        return False, "Tesseract не найден. Установка: winget install UB-Mannheim.TesseractOCR"
    if not (LOCAL_TESSDATA / "rus.traineddata").exists():
        return False, f"Нет русского языкового пакета — ожидался файл {LOCAL_TESSDATA / 'rus.traineddata'}"
    pytesseract.pytesseract.tesseract_cmd = str(exe)
    # Путь репозитория содержит пробел ("Рабочий стол") — передача через config
    # ("--tessdata-dir <путь>") ломает разбор аргументов командной строки Windows.
    # Переменная окружения надёжнее: subprocess наследует её без токенизации пути.
    os.environ["TESSDATA_PREFIX"] = str(LOCAL_TESSDATA)
    return True, ""


def extract_text(image_bytes: bytes) -> str:
    ok, reason = is_available()
    if not ok:
        raise RuntimeError(reason)
    image = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(image, lang="rus")


CYRILLIC_WORD = r"[А-ЯЁ][а-яёА-ЯЁ\-]+"


def _after_label(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def parse_passport(text: str) -> dict:
    """Лучшее возможное извлечение, не гарантия. §7 handoff: ошибка ввода флага/поля
    должна быть видна человеку до подписания — отсюда review-экран в main.py, не здесь."""
    result = {"full_name": "", "passport_data": "", "registration_address": ""}

    surname = _after_label(text, r"Фамилия[^\n]*\n\s*([А-ЯЁ\-]+)")
    given = _after_label(text, r"Имя[^\n]*\n\s*([А-ЯЁ\-]+)")
    patronymic = _after_label(text, r"Отчество[^\n]*\n\s*([А-ЯЁ\-]+)")
    if surname and given:
        result["full_name"] = " ".join(x for x in [surname, given, patronymic] if x).title()
    else:
        m = re.search(rf"({CYRILLIC_WORD})\s+({CYRILLIC_WORD})\s+({CYRILLIC_WORD})", text)
        if m:
            result["full_name"] = " ".join(m.groups())

    m = re.search(r"(\d{2}\s?\d{2})\s+(\d{6})", text)
    if m:
        result["passport_data"] = f"{m.group(1)} {m.group(2)}"

    addr = _after_label(text, r"(?:МЕСТО ЖИТЕЛЬСТВА|ЗАРЕГИСТРИРОВАН[А-Я]*)[^\n]*\n\s*([^\n]+)")
    if addr:
        result["registration_address"] = addr

    return result


def parse_egrn(text: str) -> dict:
    result = {"address": "", "cadastral_number": "", "area": "", "ownership_basis": ""}

    m = re.search(r"\d{2}:\d{2}:\d{6,7}:\d+", text)
    if m:
        result["cadastral_number"] = m.group(0)

    addr = _after_label(text, r"[Аа]дрес[^:\n]*[:\n]\s*([^\n]+)")
    if addr:
        result["address"] = addr

    area = _after_label(text, r"[Пп]лощадь[^:\n]*[:\n]\s*([\d.,]+)")
    if area:
        result["area"] = area.replace(",", ".")

    basis = _after_label(text, r"(?:[Оо]снован|[Дд]окумент[ы\-]?\s*основани\w*)[^\n]*\n?\s*([^\n]+)")
    if basis:
        result["ownership_basis"] = basis

    return result
