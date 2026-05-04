"""Агент-аналитик на Gemini 2.5 Flash с инструментом Code Execution.

Поток: загружаем локальный файл в Gemini Files API, делаем generate_content
с tools=[Tool(code_execution=...)] — модель пишет и выполняет Python внутри
одного вызова, при необходимости перегенерирует код. Из ответа собираем
parts: текст, executable_code, stdout, PNG.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from bot.prompts import ANALYST_SYSTEM, build_user_block

log = logging.getLogger(__name__)


@dataclass
class AgentResult:
    text: str
    code_blocks: list[str] = field(default_factory=list)
    stdout_blocks: list[str] = field(default_factory=list)
    images: list[bytes] = field(default_factory=list)
    usage_in: int = 0
    usage_out: int = 0
    error: str | None = None


def _collect_outputs(resp) -> AgentResult:
    text_chunks: list[str] = []
    code_blocks: list[str] = []
    stdout_blocks: list[str] = []
    images: list[bytes] = []

    candidate = resp.candidates[0]
    for part in candidate.content.parts or []:
        if getattr(part, "text", None):
            text_chunks.append(part.text)
        if getattr(part, "executable_code", None):
            code_blocks.append(part.executable_code.code)
        if getattr(part, "code_execution_result", None):
            out = part.code_execution_result.output or ""
            if out.strip():
                stdout_blocks.append(out)
        inline = getattr(part, "inline_data", None)
        if inline and inline.mime_type and inline.mime_type.startswith("image/"):
            images.append(inline.data)

    usage = getattr(resp, "usage_metadata", None)
    return AgentResult(
        text="\n".join(text_chunks).strip(),
        code_blocks=code_blocks,
        stdout_blocks=stdout_blocks,
        images=images,
        usage_in=getattr(usage, "prompt_token_count", 0) or 0,
        usage_out=getattr(usage, "candidates_token_count", 0) or 0,
    )


async def upload_file(
    client: genai.Client, path: str, display_name: str | None = None
):
    """Загружает локальный файл в Gemini Files API."""
    file_obj = await client.aio.files.upload(
        file=path,
        config=types.UploadFileConfig(display_name=display_name or os.path.basename(path)),
    )
    for _ in range(20):
        state = getattr(file_obj, "state", None)
        state_name = str(state).split(".")[-1] if state else ""
        if state_name == "ACTIVE":
            break
        if state_name == "FAILED":
            raise RuntimeError(f"Files API вернул FAILED для {file_obj.name}")
        await asyncio.sleep(0.5)
        file_obj = await client.aio.files.get(name=file_obj.name)
    return file_obj


async def analyse(
    client: genai.Client,
    file_path: str,
    user_instruction: str,
    model: str | None = None,
) -> AgentResult:
    """Запускает агентный анализ. Возвращает текст + графики + код."""
    model = model or os.environ.get("BOT_AGENT_MODEL", "gemini-2.5-flash")
    try:
        file_obj = await upload_file(client, file_path)
    except Exception as exc:
        log.exception("file upload failed")
        return AgentResult(text="", error=f"Не удалось загрузить файл в Gemini: {exc}")

    user_text = build_user_block(user_instruction)
    parts = [
        types.Part.from_uri(file_uri=file_obj.uri, mime_type=file_obj.mime_type),
        types.Part.from_text(text=user_text),
    ]

    config = types.GenerateContentConfig(
        system_instruction=ANALYST_SYSTEM,
        tools=[types.Tool(code_execution=types.ToolCodeExecution())],
        temperature=0.4,
        max_output_tokens=8192,
    )

    try:
        resp = await client.aio.models.generate_content(
            model=model,
            contents=parts,
            config=config,
        )
    except Exception as exc:
        log.exception("generate_content failed")
        return AgentResult(text="", error=f"Сбой при обращении к Gemini: {exc}")
    finally:
        try:
            await client.aio.files.delete(name=file_obj.name)
        except Exception:
            pass

    return _collect_outputs(resp)
