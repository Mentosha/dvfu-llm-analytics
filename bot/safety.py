"""Harmlessness-screen пользовательской инструкции через лёгкую модель.

Сами данные файла не проверяем: они идут через File API отдельной Part,
а не как текст промпта.
"""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import types
from pydantic import BaseModel

from bot.prompts import GUARD_SYSTEM

log = logging.getLogger(__name__)


class GuardVerdict(BaseModel):
    is_harmful: bool
    reason: str


async def screen_user_instruction(
    client: genai.Client, instruction: str
) -> GuardVerdict:
    """Возвращает вердикт по тексту, который пользователь приложил к файлу."""
    if not instruction.strip():
        return GuardVerdict(is_harmful=False, reason="empty")

    model = os.environ.get("BOT_GUARD_MODEL", "gemini-2.5-flash-lite")
    config = types.GenerateContentConfig(
        system_instruction=GUARD_SYSTEM,
        response_mime_type="application/json",
        response_schema=GuardVerdict,
        temperature=0.0,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=200,
    )
    try:
        resp = await client.aio.models.generate_content(
            model=model,
            contents=f"<user_instruction>\n{instruction}\n</user_instruction>",
            config=config,
        )
        return GuardVerdict.model_validate_json(resp.text)
    except Exception as exc:
        log.warning("guard screen failed: %s", exc)
        return GuardVerdict(is_harmful=False, reason=f"guard error: {exc}")


ALLOWED_EXTS = {".csv", ".tsv", ".xlsx", ".xls", ".parquet"}


def is_allowed_extension(filename: str) -> bool:
    name = (filename or "").lower()
    return any(name.endswith(ext) for ext in ALLOWED_EXTS)


def too_big(size_bytes: int, max_mb: int) -> bool:
    return size_bytes > max_mb * 1024 * 1024
