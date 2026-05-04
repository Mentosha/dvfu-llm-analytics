"""Генератор синтетических описаний товаров в стиле Dewu/Poizon (得物).

Запуск:
    python -m scraper.synthetic --output pipeline/example_input.csv --count 30

Создаёт CSV: id, raw_title, raw_description, raw_price, source_url.

Реалистичный шум:
- заголовки на смеси китайского/английского/русского;
- цены в CNY/RUB/USD с разной нотацией;
- описания иногда неполные, иногда с лишними мусорными токенами;
- бренды в разных регистрах с возможными опечатками.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Item:
    raw_title: str
    raw_description: str
    raw_price: str
    source_url: str


SNEAKERS = [
    ("Nike Air Jordan 1 Retro High OG", "Chicago", "sneakers", ["red", "white", "black"]),
    ("Nike Dunk Low", "Panda", "sneakers", ["black", "white"]),
    ("Adidas Yeezy Boost 350 V2", "Zebra", "sneakers", ["white", "black"]),
    ("Nike Air Force 1 '07", "Triple White", "sneakers", ["white"]),
    ("New Balance 550", "White Green", "sneakers", ["white", "green"]),
    ("Nike SB Dunk Low", "Travis Scott", "sneakers", ["brown", "olive"]),
    ("Adidas Samba OG", "Cloud White", "sneakers", ["white", "black"]),
    ("Asics Gel-1130", "Cream Pink", "sneakers", ["cream", "pink"]),
    ("Salomon XT-6", "Phantom Black", "sneakers", ["black"]),
    ("Nike Air Max 90", "Infrared", "sneakers", ["grey", "red"]),
    ("Jordan 4 Retro", "Bred", "sneakers", ["black", "red"]),
    ("Yeezy Slide", "Bone", "sneakers", ["beige"]),
    ("Adidas Campus 00s", "Core Black", "sneakers", ["black", "white"]),
    ("Onitsuka Tiger Mexico 66", "White Blue", "sneakers", ["white", "blue"]),
    ("Nike Cortez", "Forrest Gump", "sneakers", ["red", "white"]),
]

APPAREL = [
    ("Stussy Basic Logo Tee", "Pigment Black", "apparel", ["black"]),
    ("Supreme Box Logo Hoodie FW23", "Heather Grey", "apparel", ["grey"]),
    ("The North Face Nuptse 700 Fill", "TNF Black", "apparel", ["black"]),
    ("Carhartt WIP Detroit Jacket", "Hamilton Brown", "apparel", ["brown"]),
    ("Essentials Fear of God Hoodie", "Stretch Limo", "apparel", ["black"]),
    ("Arc'teryx Beta LT Jacket", "Black Sapphire", "apparel", ["dark blue"]),
    ("Patagonia Synchilla Snap-T", "Oatmeal", "apparel", ["beige", "brown"]),
    ("Comme des Garçons Play Tee", "White", "apparel", ["white"]),
]

BAGS_ACC = [
    ("Goyard St. Louis PM Tote", "Black", "bag", ["black"]),
    ("Prada Re-Edition 2005 Nylon", "Black", "bag", ["black"]),
    ("LV Pochette Métis", "Monogram", "bag", ["brown"]),
    ("AirPods Pro 2", "USB-C", "accessory", ["white"]),
    ("Casio G-Shock GA-2100", "Casioak", "accessory", ["black"]),
    ("Apple Watch Ultra 2", "Titanium", "accessory", ["silver"]),
    ("Ray-Ban Wayfarer Classic", "Black", "accessory", ["black"]),
]

ALL_PRODUCTS = SNEAKERS + APPAREL + BAGS_ACC

DESCRIPTION_TEMPLATES = [
    "{brand} {model}, цвет {color}. Размер {size}, состояние {cond}. {extra}",
    "全新现货 {brand} {model} {color} EU{size_eu} 100% authentic poizon verified",
    "В наличии {brand} {model} {color}. {gender_desc}. Размер US {size_us}. Поставка из Китая через Dewu.",
    "{brand} {model} {color} | {cond} | размер {size} | {extra}",
    "Limited release {brand} {model} {color}. Box+tags. Shipped from Shanghai 24h.",
    "{brand} {model} ({color}). Отправка из Москвы, оригинал 100%, чек DEWU прилагается.",
    "{brand} {model}, {extra}. Только новые, проверка от Poizon. {gender_desc}.",
    "Мужские {brand} {model} цвет {color}, размер EU {size_eu} / US {size_us}. {cond}.",
]

EXTRAS = [
    "В коробке, со всеми наклейками и бирками",
    "Комплект полный: коробка, запасные шнурки, чек",
    "Без коробки",
    "Носились пару раз, видимых дефектов нет",
    "Идеальное состояние, NIB",
    "Состояние 9.5/10",
    "100% оригинал, гарантия Dewu",
    "Доставка авиа из Шанхая 7-10 дней",
    "Проверка SneakerCheck пройдена",
    "Сток из материкового Китая",
]

GENDER_DESCRIPTIONS = {
    "male": ["мужские", "мужская модель", "men's", "for men"],
    "female": ["женские", "женская модель", "women's"],
    "unisex": ["унисекс", "unisex", "подходит и мужчинам и женщинам"],
}

PRICE_FORMATS_CNY = ["¥{p}", "{p} CNY", "{p}元", "￥{p}.00"]
PRICE_FORMATS_RUB = ["{p} ₽", "{p} руб.", "{p}руб", "{p} RUB"]
PRICE_FORMATS_USD = ["${p}", "USD {p}", "{p}$", "{p} USD"]


def cny_to_rub(cny: float) -> float:
    return round(cny * 12.5)  # курс ~12-13 ₽ за юань


def cny_to_usd(cny: float) -> float:
    return round(cny * 0.14, 2)


def gen_size(category: str) -> tuple[str, str, str]:
    """Возвращает (size_str_for_template, size_us, size_eu)."""
    if category == "sneakers":
        eu = random.choice([38, 39, 40, 41, 42, 43, 44, 45])
        us = round(eu - 32.5, 1)
        return (f"EU{eu}", str(us), str(eu))
    if category == "apparel":
        return (random.choice(["S", "M", "L", "XL"]), "-", "-")
    return ("-", "-", "-")


def pick_gender(category: str) -> str:
    if category == "sneakers":
        return random.choices(["male", "female", "unisex"], weights=[5, 2, 3])[0]
    if category == "apparel":
        return random.choices(["male", "female", "unisex"], weights=[5, 1, 4])[0]
    return "unisex"


def pick_condition() -> str:
    return random.choices(["new", "used"], weights=[8, 2])[0]


def gen_price_str(category: str) -> str:
    base_cny = {
        "sneakers": random.randint(800, 4500),
        "apparel": random.randint(300, 2500),
        "bag": random.randint(2000, 25000),
        "accessory": random.randint(400, 6000),
    }[category]
    currency = random.choices(["CNY", "RUB", "USD"], weights=[5, 4, 1])[0]
    if currency == "CNY":
        return random.choice(PRICE_FORMATS_CNY).format(p=base_cny)
    if currency == "RUB":
        return random.choice(PRICE_FORMATS_RUB).format(p=cny_to_rub(base_cny))
    return random.choice(PRICE_FORMATS_USD).format(p=cny_to_usd(base_cny))


def gen_item(idx: int) -> Item:
    brand_full, colorway, category, color_options = random.choice(ALL_PRODUCTS)
    brand_parts = brand_full.split(" ", 1)
    brand = brand_parts[0]
    model = brand_parts[1] if len(brand_parts) > 1 else ""
    color = random.choice(color_options)
    size, size_us, size_eu = gen_size(category)
    gender = pick_gender(category)
    condition = pick_condition()
    cond_text = "новые в коробке" if condition == "new" else "б/у в хорошем состоянии"

    title_variants = [
        f"{brand_full} {colorway}",
        f"[现货] {brand_full} {colorway} {color}",
        f"{brand} {model} '{colorway}'",
        f"{brand_full.upper()} - {colorway} ({color})",
        f"{brand_full} {colorway} | size {size}",
    ]
    title = random.choice(title_variants)

    description = random.choice(DESCRIPTION_TEMPLATES).format(
        brand=brand,
        model=f"{model} {colorway}".strip(),
        color=color,
        size=size,
        size_us=size_us,
        size_eu=size_eu,
        cond=cond_text,
        gender_desc=random.choice(GENDER_DESCRIPTIONS[gender]),
        extra=random.choice(EXTRAS),
    )

    price = gen_price_str(category)
    source_url = f"https://dewu.com/item/{random.randint(10000000, 99999999)}"

    return Item(raw_title=title, raw_description=description, raw_price=price, source_url=source_url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Генератор синтетических товаров в стиле Dewu")
    parser.add_argument("--output", required=True, help="Куда писать CSV")
    parser.add_argument("--count", type=int, default=30, help="Сколько товаров (default 30)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed для воспроизводимости")
    args = parser.parse_args()

    random.seed(args.seed)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "raw_title", "raw_description", "raw_price", "source_url"])
        writer.writeheader()
        for i in range(1, args.count + 1):
            it = gen_item(i)
            writer.writerow({
                "id": i,
                "raw_title": it.raw_title,
                "raw_description": it.raw_description,
                "raw_price": it.raw_price,
                "source_url": it.source_url,
            })

    print(f"Wrote {args.count} synthetic items to {output}")


if __name__ == "__main__":
    main()
