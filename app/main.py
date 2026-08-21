"""Веб-форма — 4 экрана (handoff §6). Локальное Flask-приложение, Вариант A: данные не
покидают компьютер Марии."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, send_file, flash, abort

from .models import Deal, Participant, DEAL_TYPES, SIDES
from . import storage
from . import ocr
from .rules import build_document_set, missing_fields
from .generator import generate_package, cross_check, GENERATED_DIR

app = Flask(__name__)
app.secret_key = "local-dev-only"  # Phase 1: один пользователь, локально — не требует секретности

# Werkzeug debug-консоль умеет выполнять произвольный Python-код при падении страницы —
# нельзя оставлять включённой, как только через форму пойдут настоящие данные клиента.
# Включается явно: LEGAL_CONSTRUCTOR_DEBUG=1 python run.py — только для разработки.
DEBUG = os.environ.get("LEGAL_CONSTRUCTOR_DEBUG") == "1"


def _get_deal_or_404(deal_id: str) -> Deal:
    deal = storage.load(deal_id)
    if deal is None:
        raise ValueError(f"Сделка {deal_id} не найдена")
    return deal


@app.route("/")
def index():
    deals = storage.list_deals()
    return render_template("index.html", deals=deals)


# --- Экран 1: Новая сделка ---------------------------------------------------

@app.route("/deals/new", methods=["GET", "POST"])
def new_deal():
    if request.method == "POST":
        deal_type = request.form.get("deal_type", "")
        if deal_type not in DEAL_TYPES:
            # Реестр шаблонов (registry.py) ищет active-шаблон по точному совпадению
            # deal_type — что угодно вне списка тихо сломало бы поиск шаблона на экране 4.
            abort(400, f"Некорректный тип сделки: {deal_type!r}. Ожидалось одно из {DEAL_TYPES}.")
        deal = Deal.create(deal_type=deal_type)
        deal.address = request.form.get("address", "")
        deal.cadastral_number = request.form.get("cadastral_number", "")
        deal.property_type = request.form.get("property_type", "")
        deal.area = request.form.get("area", "")
        deal.rooms = request.form.get("rooms", "")
        deal.ownership_basis = request.form.get("ownership_basis", "")
        deal.encumbrances = request.form.get("encumbrances", "")
        storage.save(deal)
        return redirect(url_for("participants", deal_id=deal.deal_id))
    ocr_ready, ocr_reason = ocr.is_available()
    return render_template(
        "screen1_deal.html", deal_types=DEAL_TYPES, draft={},
        ocr_ready=ocr_ready, ocr_reason=ocr_reason,
    )


@app.route("/deals/scan-egrn", methods=["POST"])
def scan_egrn():
    """Распознаёт фото выписки ЕГРН, возвращает Экран 1 с предзаполненными (не сохранёнными)
    полями — Мария проверяет/правит и только потом жмёт «Далее» (§7: человек видит ошибку
    ввода до того, как она попадёт в сделку)."""
    ocr_ready, ocr_reason = ocr.is_available()
    draft: dict = {}
    error = None
    if not ocr_ready:
        error = ocr_reason
    else:
        file = request.files.get("photo")
        # Не "if file" — bool(FileStorage) в Werkzeug равен bool(filename), а не
        # наличию содержимого. При вставке из буфера/перетаскивании имя файла может
        # быть пустым, хотя байты реально есть — "if file" тогда ложно считает файл
        # отсутствующим и теряет его (найдено 2026-08-21, воспроизведено отладкой).
        data = file.read() if file is not None else b""
        if not data:
            error = "Файл не выбран"
        else:
            try:
                text = ocr.extract_text(data)
                draft = ocr.parse_egrn(text)
            except ocr.OcrError as exc:
                error = str(exc)  # уже понятный текст, см. ocr.py
            except Exception:
                error = "Не удалось прочитать файл. Попробуйте другой файл (JPG, PNG или PDF) или пересканируйте документ."
    return render_template(
        "screen1_deal.html", deal_types=DEAL_TYPES, draft=draft,
        ocr_ready=ocr_ready, ocr_reason=ocr_reason, ocr_error=error,
    )


# --- Экран 2: Участники -------------------------------------------------------

@app.route("/deals/<deal_id>/participants", methods=["GET", "POST"])
def participants(deal_id: str):
    deal = _get_deal_or_404(deal_id)
    if request.method == "POST":
        side = request.form.get("side", "")
        if side not in SIDES:
            abort(400, f"Некорректная сторона участника: {side!r}. Ожидалось одно из {SIDES}.")
        p = Participant.create(side=side)
        p.full_name = request.form.get("full_name", "")
        p.passport_data = request.form.get("passport_data", "")
        p.registration_address = request.form.get("registration_address", "")
        p.contact = request.form.get("contact", "")
        p.representative = request.form.get("representative", "")
        p.ownership_share = request.form.get("ownership_share", "")
        p.is_married = "is_married" in request.form
        p.is_minor = "is_minor" in request.form
        p.has_other_co_owners = "has_other_co_owners" in request.form
        deal.participants.append(p)
        storage.save(deal)
        return redirect(url_for("participants", deal_id=deal.deal_id))
    ocr_ready, ocr_reason = ocr.is_available()
    return render_template(
        "screen2_participants.html", deal=deal, sides=SIDES, draft={},
        ocr_ready=ocr_ready, ocr_reason=ocr_reason,
    )


@app.route("/deals/<deal_id>/participants/scan", methods=["POST"])
def scan_passport(deal_id: str):
    """Распознаёт фото паспорта, возвращает Экран 2 с предзаполненной (не сохранённой)
    формой добавления участника — та же логика проверки перед сохранением, что и в §7."""
    deal = _get_deal_or_404(deal_id)
    ocr_ready, ocr_reason = ocr.is_available()
    draft: dict = {}
    error = None
    if not ocr_ready:
        error = ocr_reason
    else:
        file = request.files.get("photo")
        data = file.read() if file else b""
        if not data:
            error = "Файл не выбран"
        else:
            try:
                text = ocr.extract_text(data)
                draft = ocr.parse_passport(text)
                draft["side"] = request.form.get("side", "")
            except ocr.OcrError as exc:
                error = str(exc)  # уже понятный текст, см. ocr.py
            except Exception:
                error = "Не удалось прочитать файл. Попробуйте другой файл (JPG, PNG или PDF) или пересканируйте документ."
    return render_template(
        "screen2_participants.html", deal=deal, sides=SIDES, draft=draft,
        ocr_ready=ocr_ready, ocr_reason=ocr_reason, ocr_error=error,
    )


@app.route("/deals/<deal_id>/participants/<participant_id>/delete", methods=["POST"])
def delete_participant(deal_id: str, participant_id: str):
    deal = _get_deal_or_404(deal_id)
    deal.participants = [p for p in deal.participants if p.participant_id != participant_id]
    storage.save(deal)
    return redirect(url_for("participants", deal_id=deal.deal_id))


# --- Экран 3: Условия сделки ---------------------------------------------------

@app.route("/deals/<deal_id>/terms", methods=["GET", "POST"])
def terms(deal_id: str):
    deal = _get_deal_or_404(deal_id)
    if request.method == "POST":
        deal.price = request.form.get("price", "")
        deal.payment_schedule = request.form.get("payment_schedule", "")
        deal.deposit = request.form.get("deposit", "")
        deal.term = request.form.get("term", "")
        deal.special_conditions = request.form.get("special_conditions", "")
        deal.agency_name = request.form.get("agency_name", deal.agency_name)
        deal.agency_inn = request.form.get("agency_inn", "")
        deal.agency_ogrn = request.form.get("agency_ogrn", "")
        deal.agency_signatory = request.form.get("agency_signatory", "")
        for p in deal.participants:
            field_name = f"commission_{p.participant_id}"
            if field_name in request.form:
                p.commission_value = request.form[field_name]
        storage.save(deal)
        return redirect(url_for("generate", deal_id=deal.deal_id))
    return render_template("screen3_terms.html", deal=deal)


# --- Экран 4: Генерация и результат --------------------------------------------

@app.route("/deals/<deal_id>/generate", methods=["GET", "POST"])
def generate(deal_id: str):
    deal = _get_deal_or_404(deal_id)
    problems = missing_fields(deal)
    tasks = build_document_set(deal)

    generated_files = None
    template_errors = None
    notes = None

    if request.method == "POST" and not problems:
        generated_files, template_errors = generate_package(deal)
        notes = cross_check(generated_files, deal)
        deal.status = "generated" if generated_files and not template_errors else deal.status
        storage.save(deal)

    existing_dir = GENERATED_DIR / deal.deal_id
    existing_files = sorted(p.name for p in existing_dir.glob("*.docx")) if existing_dir.exists() else []

    return render_template(
        "screen4_generate.html",
        deal=deal,
        problems=problems,
        tasks=tasks,
        generated_files=generated_files,
        template_errors=template_errors,
        notes=notes,
        existing_files=existing_files,
    )


@app.route("/deals/<deal_id>/download/<path:filename>")
def download(deal_id: str, filename: str):
    path = GENERATED_DIR / deal_id / filename
    return send_file(path, as_attachment=True)


@app.route("/deals/<deal_id>/download-all")
def download_all(deal_id: str):
    deal_dir = GENERATED_DIR / deal_id
    archive_base = GENERATED_DIR / f"{deal_id}_комплект"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(deal_dir))
    return send_file(archive_path, as_attachment=True, download_name=f"комплект_{deal_id}.zip")


if __name__ == "__main__":
    app.run(debug=DEBUG, port=5001)
