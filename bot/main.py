"""Entry point Telegram-бота. Запуск: python -m bot.main"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from bot.gemini_client import make_client
from bot.handlers import router


def _make_session() -> AiohttpSession:
    proxy = (os.environ.get("TELEGRAM_PROXY_URL") or os.environ.get("LLM_PROXY_URL") or "").strip()
    return AiohttpSession(proxy=proxy) if proxy else AiohttpSession()


def setup_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.INFO)


async def main() -> None:
    load_dotenv()
    setup_logging()
    log = logging.getLogger("bot")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN не задан в окружении (см. .env.example)")

    gemini = make_client()
    log.info("Gemini client ready (proxy=%s)", bool(os.environ.get("LLM_PROXY_URL")))

    session = _make_session()
    bot = Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    me = await bot.get_me()
    log.info("Logged in as @%s id=%s", me.username, me.id)

    dp = Dispatcher()
    dp.include_router(router)

    try:
        await dp.start_polling(bot, gemini=gemini)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
