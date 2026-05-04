from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Category = Literal["sneakers", "apparel", "bag", "accessory", "other"]
Currency = Literal["CNY", "RUB", "USD", "EUR"]
Gender = Literal["male", "female", "unisex", "unknown"]
Condition = Literal["new", "used", "unknown"]


class Product(BaseModel):
    """Извлечённые характеристики товара."""

    brand: str = Field(description="Бренд (Nike, Adidas, Supreme, ...)")
    model: str | None = Field(
        default=None, description="Название модели/коллекции, если есть"
    )
    category: Category = Field(description="Категория товара")
    price_value: float = Field(description="Числовая цена в указанной валюте")
    currency: Currency = Field(description="Валюта цены")
    color: str | None = Field(default=None, description="Цвет товара одним словом на английском")
    size: str | None = Field(
        default=None, description="Размер как указан в описании (EU/US/буква)"
    )
    material: str | None = Field(default=None, description="Материал, если упомянут")
    gender: Gender = Field(description="Целевая аудитория")
    condition: Condition = Field(description="Состояние товара")
    key_features: list[str] = Field(
        default_factory=list,
        description="До 5 ключевых особенностей короткими фразами",
        max_length=5,
    )
