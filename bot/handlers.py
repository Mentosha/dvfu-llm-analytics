from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, Message
from google import genai

from bot.agent import analyse
from bot.prompts import HELP, LIMITS_TEMPLATE, WELCOME
from bot.safety import is_allowed_extension, screen_user_instruction, too_big
from bot.storage import allow, pop_pending, set_pending

log = logging.getLogger(__name__)
router = Router(name="main")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def _allowed_users() -> frozenset[int]:
    raw = os.environ.get("ALLOWED_USERS", "").strip()
    if not raw:
        return frozenset()
    out: set[int] = set()
    for part in raw.split(","):
        try:
            out.add(int(part.strip()))
        except ValueError:
            continue
    return frozenset(out)


def _is_user_allowed(user_id: int) -> bool:
    allowed = _allowed_users()
    return not allowed or user_id in allowed


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME, parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP, parse_mode="Markdown")


@router.message(Command("limits"))
async def cmd_limits(message: Message) -> None:
    await message.answer(
        LIMITS_TEMPLATE.format(
            max_mb=_env_int("MAX_FILE_SIZE_MB", 10),
            max_chars=_env_int("MAX_INSTRUCTION_CHARS", 1000),
            rate=_env_int("RATE_LIMIT_PER_HOUR", 3),
        ),
        parse_mode="Markdown",
    )


@router.message(F.document)
async def on_document(message: Message, gemini: genai.Client) -> None:
    user_id = message.from_user.id

    if not _is_user_allowed(user_id):
        await message.answer("⛔ Доступ ограничен.")
        return

    rate = _env_int("RATE_LIMIT_PER_HOUR", 3)
    ok, retry_after = allow(user_id, rate)
    if not ok:
        await message.answer(
            f"⏳ Лимит {rate} запросов в час исчерпан. Попробуйте через "
            f"{retry_after // 60} мин."
        )
        return

    doc = message.document
    if not is_allowed_extension(doc.file_name or ""):
        await message.answer(
            "⚠️ Поддерживаются только: .csv, .tsv, .xlsx, .xls, .parquet"
        )
        return

    max_mb = _env_int("MAX_FILE_SIZE_MB", 10)
    if too_big(doc.file_size or 0, max_mb):
        await message.answer(f"📦 Файл слишком большой. Максимум — {max_mb} МБ.")
        return

    instruction = (message.caption or "").strip()
    pending = pop_pending(user_id)
    if not instruction and pending.get("instruction"):
        instruction = pending["instruction"]

    max_chars = _env_int("MAX_INSTRUCTION_CHARS", 1000)
    if len(instruction) > max_chars:
        await message.answer(
            f"📝 Инструкция слишком длинная ({len(instruction)} символов, "
            f"максимум {max_chars}). Сократите и пришлите файл снова."
        )
        return

    progress = await message.answer("🔍 Принял файл, проверяю и запускаю анализ…")

    keepalive_task = asyncio.create_task(_keepalive(message, progress))
    tmp_path: Path | None = None
    try:
        verdict = await screen_user_instruction(gemini, instruction)
        if verdict.is_harmful:
            await progress.edit_text(
                "🚫 Инструкция выглядит как попытка обхода правил. "
                "Пожалуйста, задайте аналитический вопрос по данным."
            )
            log.warning("guard blocked user=%s reason=%s", user_id, verdict.reason)
            return

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(doc.file_name).suffix
        ) as tmp:
            tmp_path = Path(tmp.name)
        await message.bot.download(doc, destination=tmp_path)

        await progress.edit_text("🧠 Запускаю агента-аналитика (это 30-120 сек)…")

        result = await analyse(gemini, str(tmp_path), instruction)

        if result.error:
            await progress.edit_text(f"❌ {result.error}")
            return

        for i, img in enumerate(result.images, 1):
            await message.answer_photo(
                BufferedInputFile(img, filename=f"chart_{i}.png"),
                caption=f"График {i}/{len(result.images)}",
            )

        report = result.text or "(модель не вернула финального текста)"
        for chunk in _chunked(report, 4000):
            await message.answer(chunk, parse_mode="Markdown")

        if result.code_blocks:
            code_text = "\n\n# === next block ===\n\n".join(result.code_blocks)
            await message.answer_document(
                BufferedInputFile(code_text.encode("utf-8"), filename="agent_code.py"),
                caption="Код, который выполнял агент",
            )

        await progress.edit_text(
            f"✅ Готово! Токенов: in={result.usage_in}, out={result.usage_out}"
        )

    except Exception:
        log.exception("on_document failed")
        await progress.edit_text("❌ Внутренняя ошибка, попробуйте ещё раз позже.")
    finally:
        keepalive_task.cancel()
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message) -> None:
    user_id = message.from_user.id
    text = (message.text or "").strip()
    max_chars = _env_int("MAX_INSTRUCTION_CHARS", 1000)
    if len(text) > max_chars:
        await message.answer(
            f"📝 Слишком длинно ({len(text)} символов, максимум {max_chars})."
        )
        return
    set_pending(user_id, instruction=text)
    await message.answer(
        "✏️ Принял инструкцию. Теперь пришлите файл — он будет проанализирован "
        "с учётом этого пожелания."
    )


async def _keepalive(message: Message, progress: Message) -> None:
    dots = 1
    try:
        while True:
            await asyncio.sleep(20)
            try:
                await progress.edit_text(
                    f"🧠 Агент анализирует данные{'.' * dots} (это может занять до 2 мин)"
                )
            except Exception:
                pass
            dots = dots % 3 + 1
    except asyncio.CancelledError:
        pass


def _chunked(text: str, n: int):
    if len(text) <= n:
        yield text
        return
    buf = []
    size = 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > n and buf:
            yield "".join(buf)
            buf, size = [], 0
        buf.append(line)
        size += len(line)
    if buf:
        yield "".join(buf)
