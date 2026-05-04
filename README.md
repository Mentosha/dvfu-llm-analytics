# DVFU LLM Analytics

Монорепо с двумя независимыми подсистемами на базе Google Gemini:

| Папка | Что делает |
|---|---|
| [`pipeline/`](pipeline/) | CLI-пайплайн: CSV-описания товаров → Gemini → структурированный JSON |
| [`bot/`](bot/) | Telegram-бот с агентной аналитикой данных через **Gemini Code Execution** |

LLM-провайдер — Google Gemini (free tier).
Прокси нужен только потому, что Google блокирует Gemini API с РФ-IP.

## Быстрый старт (локально)

```bash
git clone https://github.com/Mentosha/dvfu-llm-analytics.git
cd dvfu-llm-analytics

cp .env.example .env
# Заполни .env: GEMINI_API_KEY (https://aistudio.google.com/apikey),
# TELEGRAM_BOT_TOKEN (@BotFather), LLM_PROXY_URL (socks5/http прокси в EU/US/Asia).

python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Пайплайн извлечения характеристик

```bash
# 1. Сгенерировать синтетический датасет в стиле Dewu
python -m scraper.synthetic --output pipeline/example_input.csv --count 30

# 2. Извлечь характеристики через Gemini
python -m pipeline.extract \
    --input  pipeline/example_input.csv \
    --output pipeline/example_output.json \
    --model  gemini-2.5-flash
```

Реальный вход и выход закоммичены:
- [pipeline/example_input.csv](pipeline/example_input.csv)
- [pipeline/example_output.json](pipeline/example_output.json)

Подробности — в [pipeline/README.md](pipeline/README.md).

### Telegram-бот

```bash
python -m bot.main
```

Пишите боту [@kortonov_analyst_bot](https://t.me/kortonov_analyst_bot) — присылайте CSV/Excel с инструкцией, получайте отчёт с графиками.

Подробности — в [bot/README.md](bot/README.md).

## Безопасность

В [bot/safety.py](bot/safety.py) собрано несколько уровней защиты от prompt-injection. Сначала пользовательская инструкция прогоняется через лёгкую гард-модель (Gemini Flash-lite), потом оборачивается в тег `<user_instruction>` — основной модели сказано не исполнять команды изнутри тега. System-prompt у агента жёсткий: блоки `<role>`, `<constraints>`, `<workflow>` запрещают смену роли, раскрытие промпта и любые задачи вне аналитики. CSV никогда не идёт в текст промпта — только через File API отдельной Part, поэтому команды в ячейках не воспринимаются как инструкции. Сверху — лимиты: размер файла, длина инструкции, 3 запроса в час на пользователя.

## Конфиденциальность

Бот сидит на бесплатном тарифе Gemini — по политике Google данные с free tier могут использоваться для обучения моделей. Бот предупреждает об этом в `/start`. Не кидайте сюда ничего личного и рабочего.

## Лимиты Gemini Code Execution

- Каждый блок выполнения кода — до **30 секунд** (модель может делать несколько шагов).
- Доступные библиотеки: `pandas`, `numpy`, `matplotlib`, `seaborn`, `scikit-learn`, `scipy`, `openpyxl`, `pillow`, `sympy` и ещё ~20.
- Интернета внутри песочницы нет.

## Стек

- **Python 3.13**
- [`google-genai`](https://pypi.org/project/google-genai/) 1.62 — официальный SDK
- [`aiogram`](https://aiogram.dev/) 3.27 — async Telegram framework
- `httpx[socks]` — для SOCKS5/HTTP прокси
- `pydantic` 2 — для `response_schema`
- `tenacity`, `aiolimiter`, `tqdm`

## Автор

Луцук Иван Дмитриевич, группа Б9123-09.03.02ацс.
