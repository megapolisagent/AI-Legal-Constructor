"""Запускается ОТДЕЛЬНЫМ процессом под venv312 (PaddlePaddle пока не поддерживает
Python 3.14, на котором работает само приложение — см. README). Берёт путь к
изображению аргументом, печатает распознанные строки в stdout после маркера
RESULT_MARKER — всё до маркера (логи модели, предупреждения) не парсится вызывающей
стороной (app/ocr.py), чтобы служебный вывод PaddleOCR не попал в текст документа.

Модели явно зафиксированы (не по lang=): PP-OCRv5_mobile_det (детекция, CPU) +
eslav_PP-OCRv5_mobile_rec (распознавание, обучена на кириллице/восточнославянских
языках) — при lang='ru' без явных имён моделей auto-подбор один раз откатился на
модель без кириллицы (см. workspace-дневник 2026-08-21). enable_mkldnn=False —
на этой машине PP-OCRv5_server_det + oneDNN падает с NotImplementedError на уровне
PaddlePaddle, mobile-модели без mkldnn работают стабильно.
"""
from __future__ import annotations

import sys

RESULT_MARKER = "===PADDLE_OCR_RESULT==="


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <image_path>", file=sys.stderr)
        sys.exit(2)
    image_path = sys.argv[1]

    from paddleocr import PaddleOCR

    ocr = PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="eslav_PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )
    result = ocr.predict(image_path)

    print(RESULT_MARKER)
    for page in result:
        texts = page.get("rec_texts") or []
        scores = page.get("rec_scores") or []
        for text, score in zip(texts, scores):
            print(f"{score:.4f}\t{text}")


if __name__ == "__main__":
    main()
