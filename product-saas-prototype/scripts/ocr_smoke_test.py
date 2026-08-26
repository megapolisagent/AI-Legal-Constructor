"""Сквозной тест OCR-пайплайна: рисует синтетическое "фото" документа (текст на
белом фоне через системный шрифт с кириллицей) и проверяет, что extract_text +
parse_passport/parse_egrn действительно вытаскивают поля. Не заменяет проверку на
настоящих фото — только доказывает, что пайплайн Tesseract -> regex работает."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont

from app import ocr

ok, reason = ocr.is_available()
print(f"OCR доступен: {ok} ({reason})")
assert ok, "OCR должен быть доступен для этого теста"

FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
font = ImageFont.truetype(FONT_PATH, 28)


def render_text_image(lines: list[str]) -> bytes:
    img = Image.new("RGB", (900, 40 * len(lines) + 40), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((20, 20 + i * 40), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


print("\n--- Паспорт ---")
passport_lines = [
    "ПАСПОРТ РОССИЙСКАЯ ФЕДЕРАЦИЯ",
    "45 07 123456",
    "Фамилия",
    "ИВАНОВА",
    "Имя",
    "ИРИНА",
    "Отчество",
    "ИВАНОВНА",
    "Пол Ж Дата рождения 01.01.1980",
]
text = ocr.extract_text(render_text_image(passport_lines))
print("Распознанный текст:\n", text)
parsed = ocr.parse_passport(text)
print("Извлечено:", parsed)
assert "ИВАНОВА" in parsed["full_name"].upper() or "Иванова" in parsed["full_name"], \
    f"Фамилия не распознана: {parsed}"
assert "4507" in parsed["passport_data"].replace(" ", "") or "123456" in parsed["passport_data"], \
    f"Номер паспорта не распознан: {parsed}"
print("PASSPORT PARSE: OK")

print("\n--- ЕГРН ---")
egrn_lines = [
    "ВЫПИСКА ИЗ ЕГРН",
    "Кадастровый номер: 77:01:0001001:1234",
    "Адрес: г. Москва, ул. Тестовая, д. 1, кв. 2",
    "Площадь: 65.4",
]
text2 = ocr.extract_text(render_text_image(egrn_lines))
print("Распознанный текст:\n", text2)
parsed2 = ocr.parse_egrn(text2)
print("Извлечено:", parsed2)
assert parsed2["cadastral_number"] == "77:01:0001001:1234", f"Кадастровый номер не распознан: {parsed2}"
print("EGRN PARSE: OK")

print("\nOCR SMOKE TEST: OK")
