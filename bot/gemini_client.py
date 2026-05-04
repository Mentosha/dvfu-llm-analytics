"""Клиент Gemini с прокси для обхода РФ-блокировки.

URL берётся из env LLM_PROXY_URL — если пуст, ходим напрямую.
"""

from __future__ import annotations

import os

import httpx
from google import genai
from google.genai import types


def make_client(api_key: str | None = None) -> genai.Client:
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY не задан в окружении")

    proxy = os.environ.get("LLM_PROXY_URL") or None
    http_options = None
    if proxy:
        http_options = types.HttpOptions(
            client_args={
                "transport": httpx.HTTPTransport(proxy=proxy),
                "timeout": 120.0,
            },
            async_client_args={
                "transport": httpx.AsyncHTTPTransport(proxy=proxy),
                "timeout": 120.0,
            },
        )
    return genai.Client(api_key=api_key, http_options=http_options)
