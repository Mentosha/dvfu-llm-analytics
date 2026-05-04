"""Читает CSV с описаниями товаров, прогоняет каждую строку через Gemini
с response_schema=Product и пишет агрегированный JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from time import perf_counter

import httpx
from aiolimiter import AsyncLimiter
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tqdm import tqdm

from pipeline.prompts import SYSTEM_PROMPT, build_user_message
from pipeline.schema import Product


def make_client() -> genai.Client:
    proxy = os.environ.get("LLM_PROXY_URL")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY не задан (см. .env.example)")
    http_options = None
    if proxy:
        http_options = types.HttpOptions(
            client_args={
                "transport": httpx.HTTPTransport(proxy=proxy),
                "timeout": 60.0,
            },
            async_client_args={
                "transport": httpx.AsyncHTTPTransport(proxy=proxy),
                "timeout": 60.0,
            },
        )
    return genai.Client(api_key=api_key, http_options=http_options)


async def extract_one(
    client: genai.Client,
    model: str,
    row: dict,
    limiter: AsyncLimiter,
) -> dict:
    """Возвращает запись с полями id/extracted/error/usage."""
    user_msg = build_user_message(
        raw_title=row["raw_title"],
        raw_description=row["raw_description"],
        raw_price=row["raw_price"],
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=Product,
        temperature=0.1,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=1024,
    )

    async def _call():
        async with limiter:
            return await client.aio.models.generate_content(
                model=model, contents=user_msg, config=config
            )

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(6),
            wait=wait_exponential(multiplier=4, min=4, max=60),
            retry=retry_if_exception_type(
                (genai_errors.APIError, httpx.HTTPError)
            ),
            reraise=True,
        ):
            with attempt:
                resp = await _call()
        product = Product.model_validate_json(resp.text)
        usage = resp.usage_metadata
        return {
            "id": row["id"],
            "extracted": product.model_dump(),
            "error": None,
            "usage": {
                "input_tokens": usage.prompt_token_count,
                "output_tokens": usage.candidates_token_count,
            },
            "source": {
                "raw_title": row["raw_title"],
                "raw_price": row["raw_price"],
            },
        }
    except ValidationError as exc:
        return {"id": row["id"], "extracted": None, "error": f"validation: {exc}"}
    except genai_errors.APIError as exc:
        return {"id": row["id"], "extracted": None, "error": f"api: {exc}"}
    except Exception as exc:
        return {"id": row["id"], "extracted": None, "error": f"unexpected: {exc!r}"}


async def run(args: argparse.Namespace) -> int:
    client = make_client()

    with open(args.input, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.limit > 0:
        rows = rows[: args.limit]

    existing: dict[str, dict] = {}
    if args.resume and Path(args.output).exists():
        try:
            with open(args.output, encoding="utf-8") as f:
                for r in json.load(f):
                    existing[str(r["id"])] = r
        except (json.JSONDecodeError, OSError):
            existing = {}
        before = len(rows)
        rows = [
            r for r in rows
            if str(r["id"]) not in existing
            or existing[str(r["id"])].get("error") is not None
        ]
        print(f"[resume] из {before} строк к обработке осталось {len(rows)}")

    rpm = args.rpm
    limiter = AsyncLimiter(rpm, time_period=60)
    sem = asyncio.Semaphore(args.parallel)

    async def with_sem(row):
        async with sem:
            return await extract_one(client, args.model, row, limiter)

    started = perf_counter()
    results: list[dict] = []
    with tqdm(total=len(rows), desc=f"Extracting [{args.model}]", ncols=90) as pbar:
        for coro in asyncio.as_completed([with_sem(r) for r in rows]):
            results.append(await coro)
            pbar.update(1)

    if args.resume and existing:
        merged = dict(existing)
        for r in results:
            merged[str(r["id"])] = r
        results = list(merged.values())

    results.sort(key=lambda r: int(r["id"]))

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    elapsed = perf_counter() - started
    ok = sum(1 for r in results if r["error"] is None)
    fail = len(results) - ok
    total_in = sum(r.get("usage", {}).get("input_tokens", 0) for r in results)
    total_out = sum(r.get("usage", {}).get("output_tokens", 0) for r in results)
    print(
        f"\nDone in {elapsed:.1f}s | model={args.model} | rows={len(results)} | "
        f"ok={ok} fail={fail} | tokens in={total_in} out={total_out}"
    )
    print(f"Output: {args.output}")
    return 0 if fail == 0 else 2


def main() -> None:
    p = argparse.ArgumentParser(description="Извлечение характеристик товаров через Gemini")
    p.add_argument("--input", required=True, help="CSV: id,raw_title,raw_description,raw_price,source_url")
    p.add_argument("--output", required=True, help="Куда писать JSON")
    p.add_argument("--model", default=os.environ.get("PIPELINE_MODEL", "gemini-2.5-flash"))
    p.add_argument("--limit", type=int, default=0, help="Сколько строк обработать (0 = все)")
    p.add_argument("--parallel", type=int, default=2)
    p.add_argument("--rpm", type=int, default=4, help="Лимит запросов в минуту (для free tier — 4)")
    p.add_argument("--resume", action="store_true", help="Перезапустить только проваленные строки из --output")
    args = p.parse_args()
    load_dotenv()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
