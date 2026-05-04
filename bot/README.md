# Telegram-бот с агентной аналитикой данных

Бот принимает CSV/Excel/Parquet, передаёт его Gemini 2.5 Flash с подключённым инструментом **Code Execution**, и возвращает текстовый отчёт + графики.

LLM сама пишет и выполняет Python-код в песочнице — анализ выполняется агентно через интерпретатор кода, а не перефразированием подставленной в промпт статистики.

## Как работает

Пользователь присылает документ (с подписью или без). Бот проверяет расширение, размер и rate-limit, прогоняет инструкцию через harmlessness-screen на Flash-lite, заливает файл в Gemini Files API и вызывает Flash с инструментом Code Execution. Модель пишет и исполняет Python внутри одного вызова — на выходе получаем текст, исполненный код, stdout и PNG-картинки графиков.

Команды бота: `/start`, `/help`, `/limits`.

Защита от prompt-injection — в [safety.py](safety.py) и [prompts.py](prompts.py). Пять техник описаны в корневом [README.md](../README.md#безопасность).

## Запуск локально

```bash
cd dvfu-llm-analytics
source .venv/bin/activate
python -m bot.main
```

## Запуск в Docker

```bash
docker compose up --build
```

## Конфиг

Все параметры в `.env` (см. `.env.example`):

| Переменная | По умолчанию | Описание |
|---|---|---|
| `GEMINI_API_KEY` | — | Ключ Gemini API |
| `TELEGRAM_BOT_TOKEN` | — | Токен бота от @BotFather |
| `LLM_PROXY_URL` | — | SOCKS5 / HTTP прокси (для обхода РФ-блокировки) |
| `BOT_AGENT_MODEL` | `gemini-2.5-flash` | Модель основного агента |
| `BOT_GUARD_MODEL` | `gemini-2.5-flash-lite` | Модель для harmlessness-screen |
| `MAX_FILE_SIZE_MB` | 10 | Лимит размера файла |
| `MAX_INSTRUCTION_CHARS` | 1000 | Лимит длины инструкции |
| `RATE_LIMIT_PER_HOUR` | 3 | Запросов в час на одного user_id |
| `ALLOWED_USERS` | (пусто) | CSV-список user_id для приватного режима |
