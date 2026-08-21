"""OCR — локальное распознавание фото паспорта/ЕГРН через PaddleOCR (Phase 1.1,
заменил Tesseract 2026-08-21 по итогам workspace/agent-runs/2026-08-21-ocr-vision-research.md
— заметно точнее на кириллице и цифрах, тот же случай с кадастровым номером, где Tesseract
промахивался, у PaddleOCR распознался верно). Данные не покидают компьютер — тот же принцип,
что и весь Вариант A (см. брифинг 2026-08-21). Точность распознавания ограничена и не
гарантируется: все извлечённые поля обязательно проходят экран проверки/правки, прежде чем
попасть в Deal (main.py) — это прямое требование владельца, не техническая деталь.

PaddlePaddle пока не публикует колёса под Python 3.14 (на котором работает само приложение) —
распознавание запускается ОТДЕЛЬНЫМ процессом в venv312/ (Python 3.12), см. README
"Распознавание фото (OCR) — отдельная установка" и scripts/paddle_ocr_worker.py."""
from __future__ import annotations

import io
import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

MAX_PDF_PAGES = 10  # выписки/паспорта — единицы страниц; защита от случайно огромного файла

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = REPO_ROOT / "venv312" / "Scripts" / "python.exe"
WORKER_SCRIPT = REPO_ROOT / "scripts" / "paddle_ocr_worker.py"
RESULT_MARKER = "===PADDLE_OCR_RESULT==="
WORKER_TIMEOUT_SEC = 120  # первый прогон включает разовую загрузку моделей — с запасом


def is_available() -> tuple[bool, str]:
    """(доступен ли OCR, причина если нет) — для честного сообщения в UI вместо падения."""
    if not VENV_PYTHON.exists():
        return False, (
            f"Не найдено окружение для распознавания ({VENV_PYTHON}). "
            "Установка — см. README, раздел «Распознавание фото (OCR)»."
        )
    if not WORKER_SCRIPT.exists():
        return False, f"Не найден скрипт распознавания ({WORKER_SCRIPT})"
    return True, ""


class OcrError(RuntimeError):
    """Текст уже готов для показа пользователю как есть (в отличие от сырых исключений
    библиотек вроде PyMuPDF/PIL, которые тоже могут оказаться RuntimeError — поэтому
    отдельный класс, не просто RuntimeError, см. main.py)."""


def _pdf_to_images(data: bytes) -> list[Image.Image]:
    import pymupdf  # локальный рендер PDF в картинку — библиотека, не внешний сервис

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise OcrError("Не удалось открыть PDF — файл повреждён или защищён паролем") from exc
    try:
        if doc.page_count == 0:
            raise OcrError("В этом PDF нет страниц")
        images = []
        for page in doc[:MAX_PDF_PAGES]:
            pix = page.get_pixmap(dpi=300)  # выше DPI — точнее распознавание мелкого шрифта
            images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
        return images
    finally:
        doc.close()


def _bytes_to_images(data: bytes) -> list[Image.Image]:
    """Понятная ошибка вместо технического текста исключения — экран показывает
    результат этой функции пользователю напрямую (main.py)."""
    if data[:4] == b"%PDF":
        try:
            return _pdf_to_images(data)
        except OcrError:
            raise
        except Exception as exc:
            raise OcrError("Не удалось открыть PDF — файл повреждён или защищён паролем") from exc
    try:
        return [Image.open(io.BytesIO(data))]
    except UnidentifiedImageError:
        raise OcrError(
            "Файл не распознан как изображение или PDF. Поддерживаются: JPG, PNG, PDF."
        )
    except Exception as exc:
        raise OcrError("Не удалось прочитать файл — попробуйте другой файл или пересканируйте документ") from exc


def _ocr_single_image(image: Image.Image) -> str:
    """Отдельный процесс venv312 на каждый вызов — простое и надёжное решение для
    низкой частоты запросов Phase 1 (несколько документов на сделку), без постоянно
    работающего сервиса, которым пришлось бы управлять отдельно."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image.convert("RGB").save(tmp, format="PNG")
        tmp_path = Path(tmp.name)
    # PYTHONIOENCODING явно, не по умолчанию: без него дочерний процесс (venv312)
    # печатает кириллицу в кодовой странице консоли Windows, а не в UTF-8, если сам
    # Flask-сервер запущен без этой переменной в своём окружении (например, обычным
    # `python run.py`) — часть кириллических слов приходила как заменяющие символы,
    # регекс-парсеры (parse_egrn/parse_passport) их не находили (найдено 2026-08-21).
    worker_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        try:
            proc = subprocess.run(
                [str(VENV_PYTHON), str(WORKER_SCRIPT), str(tmp_path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=WORKER_TIMEOUT_SEC, env=worker_env,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrError("Распознавание заняло слишком много времени — попробуйте ещё раз") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    if proc.returncode != 0 or RESULT_MARKER not in proc.stdout:
        raise OcrError("Не удалось распознать файл — попробуйте другой файл или пересканируйте документ")

    _, _, after_marker = proc.stdout.partition(RESULT_MARKER)
    lines = []
    for line in after_marker.strip().splitlines():
        # формат строки воркера: "score\tтекст" (score сейчас не используется парсерами
        # полей ниже — задел под подсветку низкой уверенности, см. handoff §7 / research §3)
        _, _, text = line.partition("\t")
        lines.append(text or line)
    return "\n".join(lines)


def extract_text(file_bytes: bytes) -> str:
    ok, reason = is_available()
    if not ok:
        raise OcrError(reason)
    if not file_bytes:
        raise OcrError("Файл пустой")
    images = _bytes_to_images(file_bytes)
    return "\n".join(_ocr_single_image(img) for img in images)


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
