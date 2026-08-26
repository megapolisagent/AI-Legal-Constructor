"""Telegram-канал к агенту «Юрист Мегаполиса» — handoff §13.3.

Мария пишет вопрос в Telegram → бот передаёт текст в claude (та же папка агента, те же
HOME.md/SOUL.md/ROUTING.md/skills, что и в интерактивной сессии) → ответ (текст и/или
новые .docx из output/) уходит обратно в тот же чат.

Работает только пока запущен сам этот процесс (локально, не облако — решение владельца
2026-08-25). Отвечает только пользователям из ALLOWED_USER_IDS (.env) — открытый бот без
списка разрешённых был бы доступен кому угодно, кто узнает его имя в Telegram.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

BOT_DIR = Path(__file__).resolve().parent
AGENT_DIR = BOT_DIR.parent  # корень "AI Legal Constructor"
OUTPUT_DIR = AGENT_DIR / "output"
SESSIONS_PATH = BOT_DIR / "sessions.json"

load_dotenv(BOT_DIR / ".env")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALLOWED_USER_IDS = {
    uid.strip() for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",") if uid.strip()
}
CLAUDE_TIMEOUT_SECONDS = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "300"))


def _resolve_claude_invocation() -> list[str]:
    """На Windows `claude` — это npm-обёртка claude.cmd/.ps1, не .exe: asyncio не может
    запустить .cmd/.ps1 напрямую (падает с WinError 2 — "не удаётся найти файл").
    Прогонять через cmd.exe (`cmd /c claude ...`) небезопасно — cmd.exe сам разбирает
    текст на команды по &, |, ^ и т.п., а текст сообщения приходит от пользователя
    Telegram. PowerShell -File передаёт аргументы буквально, без этого риска."""
    override = os.environ.get("CLAUDE_BIN")
    if override:
        return [override]
    if os.name == "nt":
        cmd_path = shutil.which("claude")
        if cmd_path and cmd_path.lower().endswith(".cmd"):
            ps1_path = cmd_path[:-4] + ".ps1"
            if Path(ps1_path).exists():
                return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", ps1_path]
    return ["claude"]


CLAUDE_INVOCATION = _resolve_claude_invocation()
TELEGRAM_MESSAGE_LIMIT = 4000  # реальный лимит Telegram — 4096, оставляем запас

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(BOT_DIR / "bot.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("legal-bot")

_locks: dict[str, asyncio.Lock] = {}


def _load_sessions() -> dict:
    if SESSIONS_PATH.exists():
        return json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
    return {}


def _save_sessions(sessions: dict) -> None:
    SESSIONS_PATH.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_output_files() -> dict[Path, float]:
    if not OUTPUT_DIR.exists():
        return {}
    return {p: p.stat().st_mtime for p in OUTPUT_DIR.rglob("*") if p.is_file()}


def _new_files_since(before: dict[Path, float]) -> list[Path]:
    after = _snapshot_output_files()
    return sorted(
        p for p, mtime in after.items()
        if p not in before or mtime > before[p]
    )


async def _run_claude(chat_id: str, text: str, sessions: dict) -> dict:
    """Один вызов агента: новая сессия на первое сообщение чата, --resume дальше —
    так Telegram-переписка соответствует одному непрерывному диалогу с агентом."""
    session_id = sessions.get(chat_id)
    cmd = CLAUDE_INVOCATION + ["-p", text, "--output-format", "json", "--permission-mode", "bypassPermissions"]
    if session_id:
        cmd += ["--resume", session_id]
    else:
        session_id = str(uuid.uuid4())
        cmd += ["--session-id", session_id]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(AGENT_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=CLAUDE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"Агент не ответил за {CLAUDE_TIMEOUT_SECONDS} сек.")

    if proc.returncode != 0:
        raise RuntimeError(f"claude завершился с ошибкой (код {proc.returncode}): {stderr.decode('utf-8', 'replace')[:500]}")

    data = json.loads(stdout.decode("utf-8"))
    sessions[chat_id] = data.get("session_id", session_id)
    _save_sessions(sessions)
    return data


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = str(update.effective_chat.id)

    if not user or str(user.id) not in ALLOWED_USER_IDS:
        await update.message.reply_text(
            "Этот бот настроен на конкретного владельца. "
            f"Ваш Telegram ID: {user.id if user else '?'} — добавьте его в ALLOWED_USER_IDS в .env, если это вы."
        )
        log.warning("Отклонено сообщение от неразрешённого user_id=%s", user.id if user else "?")
        return

    if not update.message or not update.message.text:
        await update.message.reply_text("Пока понимаю только текстовые сообщения.")
        return

    text = update.message.text
    lock = _locks.setdefault(chat_id, asyncio.Lock())

    async with lock:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        sessions = _load_sessions()
        before = _snapshot_output_files()
        start = time.monotonic()

        try:
            data = await _run_claude(chat_id, text, sessions)
        except Exception as exc:
            log.exception("Ошибка при обращении к агенту")
            await update.message.reply_text(f"Не получилось получить ответ: {exc}")
            return

        log.info("chat_id=%s заняло %.1fs, cost=$%.4f", chat_id, time.monotonic() - start, data.get("total_cost_usd", 0))

        result_text = data.get("result") or "(агент ничего не ответил текстом)"
        for i in range(0, len(result_text), TELEGRAM_MESSAGE_LIMIT):
            await update.message.reply_text(result_text[i:i + TELEGRAM_MESSAGE_LIMIT])

        for path in _new_files_since(before):
            try:
                with open(path, "rb") as f:
                    await update.message.reply_document(document=f, filename=path.name)
            except Exception:
                log.exception("Не смог отправить файл %s", path)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан — заполните telegram_bot/.env (см. .env.example)")
    if not ALLOWED_USER_IDS:
        log.warning("ALLOWED_USER_IDS пуст — бот пока никому не будет отвечать по существу (это ожидаемо на первом запуске)")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Бот запущен, слушаю сообщения…")
    app.run_polling()


if __name__ == "__main__":
    main()
