# Пайплайн извлечения характеристик товаров

CSV с неформальными описаниями товаров → Gemini Flash с `response_schema` → структурированный JSON.

## Как это работает

На вход — CSV вида:

```csv
id,raw_title,raw_description,raw_price,source_url
1,"Nike Air Jordan 1 Chicago","新现货 Nike Air Jordan 1 Retro High OG 'Chicago' EU42 100% authentic poizon","¥1499","https://dewu.com/item/12345678"
```

И превращает в JSON:

```json
{
  "id": "1",
  "extracted": {
    "brand": "Nike",
    "model": "Air Jordan 1 Retro High OG Chicago",
    "category": "sneakers",
    "price_value": 1499,
    "currency": "CNY",
    "color": "red",
    "size": "EU42",
    "material": null,
    "gender": "unisex",
    "condition": "new",
    "key_features": ["100% authentic", "Poizon verified", "OG colorway"]
  },
  "error": null,
  "usage": {"input_tokens": 200, "output_tokens": 90}
}
```

## Запуск

```bash
# 1. Источник данных — синтетический генератор в стиле Dewu (всегда работает)
python -m scraper.synthetic --output pipeline/example_input.csv --count 30

# 2. Извлечение
python -m pipeline.extract \
    --input  pipeline/example_input.csv \
    --output pipeline/example_output.json \
    --model  gemini-2.5-flash
```

Аргументы `pipeline.extract`:
- `--input` - путь к CSV (обязательный)
- `--output` - куда писать JSON (обязательный)
- `--model` - модель Gemini (default: `gemini-2.5-flash`)
- `--limit N` - обработать только первые N строк (0 = все)
- `--parallel K` - сколько одновременных запросов (default: 2)
- `--rpm N` - лимит запросов в минуту (default: 4, под free tier)
- `--resume` - перепрогнать только проваленные строки из старого `--output`

## Альтернативный источник: реальный Dewu

```bash
python -m scraper.dewu --output data/dewu_raw.csv --queries "air jordan" "yeezy"
```

Это **best-effort** парсер. У Dewu подпись запросов и геоблок, поэтому модуль может вернуть 0 строк — в этом случае используйте синтетический генератор.

## Защита от инъекций

System-prompt запрещает модели выполнять инструкции, которые могут попасться в полях CSV. Сами поля оборачиваются в `<product_data>...</product_data>`, чтобы модель видела границу между данными и командой.

## Вывод в JSON

Через `response_schema=Product` (Pydantic) Gemini сам валидирует ответ по схеме — на выходе всегда корректный JSON. См. [pipeline/schema.py](schema.py).

## Что лежит в примерах

- [example_input.csv](example_input.csv) - 30 синтетических товаров со смесью языков и валют.
- [example_output.json](example_output.json) - реальный вывод пайплайна на этих данных.
