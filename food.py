#!/usr/bin/env python3
"""Учёт продуктов, рецептов, заготовок и калорий."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

BASIS_LABEL = {"g": "г", "ml": "мл", "pcs": "шт"}
NUTRIENT_KEYS = ("kcal", "protein", "fat", "carbs")
NUTRIENT_LABEL = {
    "kcal": "ккал",
    "protein": "белки",
    "fat": "жиры",
    "carbs": "углеводы",
}


class DataError(Exception):
    pass


def load_json(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DataError(f"Нет файла {path}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataError(f"{path.name}: не читается JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise DataError(f"{path.name}: ожидался объект JSON")
    return data


def load_all(data_dir: Path = DATA) -> dict:
    products = load_json(data_dir / "products.json").get("products", [])
    recipes = load_json(data_dir / "recipes.json").get("recipes", [])
    preps = load_json(data_dir / "preps.json").get("preps", [])
    return {"products": products, "recipes": recipes, "preps": preps}


def _as_number(value, label: str, errors: list[str]):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{label}: нужно число")
        return None
    return float(value)


def _require_str(item: dict, key: str, label: str, errors: list[str]) -> str | None:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: нужно непустое поле {key}")
        return None
    return value.strip()


def _unique_ids(items: list, label: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label} #{index}: ожидался объект")
            continue
        raw_id = item.get("id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            errors.append(f"{label} #{index}: пустой id")
            continue
        item_id = raw_id.strip()
        if item_id in seen:
            errors.append(f"{label}: повтор id {item_id}")
        seen.add(item_id)


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    products = data.get("products")
    recipes = data.get("recipes")
    preps = data.get("preps")
    if not isinstance(products, list):
        errors.append("products: ожидался список")
        products = []
    if not isinstance(recipes, list):
        errors.append("recipes: ожидался список")
        recipes = []
    if not isinstance(preps, list):
        errors.append("preps: ожидался список")
        preps = []

    _unique_ids(products, "продукт", errors)
    _unique_ids(recipes, "рецепт", errors)
    _unique_ids(preps, "заготовка", errors)

    product_ids: set[str] = set()
    for index, product in enumerate(products, start=1):
        if not isinstance(product, dict):
            continue
        label = f"продукт {product.get('id') or index}"
        item_id = _require_str(product, "id", label, errors)
        _require_str(product, "name", label, errors)
        if item_id:
            product_ids.add(item_id)
        basis = product.get("basis")
        if basis not in BASIS_LABEL:
            errors.append(f"{label}: basis должен быть g, ml или pcs")
        quantity = _as_number(product.get("quantity"), f"{label}.quantity", errors)
        if quantity is not None and quantity < 0:
            errors.append(f"{label}: quantity не может быть отрицательным")
        if "minQuantity" in product and product.get("minQuantity") is not None:
            minimum = _as_number(product.get("minQuantity"), f"{label}.minQuantity", errors)
            if minimum is not None and minimum < 0:
                errors.append(f"{label}: minQuantity не может быть отрицательным")
        for key in NUTRIENT_KEYS:
            if key in product and product.get(key) is not None:
                nutrient = _as_number(product.get(key), f"{label}.{key}", errors)
                if nutrient is not None and nutrient < 0:
                    errors.append(f"{label}: {key} не может быть отрицательным")

    recipe_ids: set[str] = set()
    for index, recipe in enumerate(recipes, start=1):
        if not isinstance(recipe, dict):
            continue
        label = f"рецепт {recipe.get('id') or index}"
        item_id = _require_str(recipe, "id", label, errors)
        _require_str(recipe, "name", label, errors)
        if item_id:
            recipe_ids.add(item_id)
        servings = _as_number(recipe.get("servings"), f"{label}.servings", errors)
        if servings is not None and servings <= 0:
            errors.append(f"{label}: servings должен быть больше нуля")
        ingredients = recipe.get("ingredients")
        if not isinstance(ingredients, list):
            errors.append(f"{label}: ingredients должен быть списком")
            continue
        for ing_index, ingredient in enumerate(ingredients, start=1):
            ing_label = f"{label}, ингредиент #{ing_index}"
            if not isinstance(ingredient, dict):
                errors.append(f"{ing_label}: ожидался объект")
                continue
            product_id = _require_str(ingredient, "productId", ing_label, errors)
            if product_id and product_id not in product_ids:
                errors.append(f"{ing_label}: нет продукта {product_id}")
            amount = _as_number(ingredient.get("amount"), f"{ing_label}.amount", errors)
            if amount is not None and amount < 0:
                errors.append(f"{ing_label}: amount не может быть отрицательным")

    for index, prep in enumerate(preps, start=1):
        if not isinstance(prep, dict):
            continue
        label = f"заготовка {prep.get('id') or index}"
        _require_str(prep, "id", label, errors)
        _require_str(prep, "name", label, errors)
        total = _as_number(prep.get("portionsTotal"), f"{label}.portionsTotal", errors)
        left = _as_number(prep.get("portionsLeft"), f"{label}.portionsLeft", errors)
        if total is not None and total <= 0:
            errors.append(f"{label}: portionsTotal должен быть больше нуля")
        if left is not None and left < 0:
            errors.append(f"{label}: portionsLeft не может быть отрицательным")
        if total is not None and left is not None and left > total:
            errors.append(f"{label}: portionsLeft больше portionsTotal")
        recipe_id = prep.get("recipeId")
        if recipe_id is not None:
            if not isinstance(recipe_id, str) or not recipe_id.strip():
                errors.append(f"{label}: recipeId должен быть строкой")
            elif recipe_id.strip() not in recipe_ids:
                errors.append(f"{label}: нет рецепта {recipe_id}")
        made_on = prep.get("madeOn")
        if made_on is not None and not _is_date(made_on):
            errors.append(f"{label}: madeOn должен быть датой ГГГГ-ММ-ДД")

    return errors


def _is_date(value) -> bool:
    if not isinstance(value, str) or len(value) != 10:
        return False
    year, sep1, month, sep2, day = value[0:4], value[4], value[5:7], value[7], value[8:10]
    if sep1 != "-" or sep2 != "-" or not (year + month + day).isdigit():
        return False
    month_n = int(month)
    day_n = int(day)
    return 1 <= month_n <= 12 and 1 <= day_n <= 31


def index_by_id(items: list[dict]) -> dict[str, dict]:
    return {item["id"].strip(): item for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def scale_nutrient(product: dict, amount: float, key: str) -> float | None:
    value = product.get(key)
    if value is None:
        return None
    if product.get("basis") == "pcs":
        return amount * float(value)
    return amount / 100.0 * float(value)


def compute_recipe_nutrition(recipe: dict, products_by_id: dict[str, dict]) -> dict:
    totals = {key: 0.0 for key in NUTRIENT_KEYS}
    seen = {key: False for key in NUTRIENT_KEYS}
    missing = {key: [] for key in NUTRIENT_KEYS}
    for ingredient in recipe.get("ingredients") or []:
        product_id = ingredient.get("productId")
        product = products_by_id.get(product_id)
        amount = float(ingredient.get("amount") or 0)
        name = product.get("name") if product else product_id
        if product is None:
            for key in NUTRIENT_KEYS:
                missing[key].append(str(name))
            continue
        for key in NUTRIENT_KEYS:
            scaled = scale_nutrient(product, amount, key)
            if scaled is None:
                missing[key].append(product.get("name") or product_id)
            else:
                totals[key] += scaled
                seen[key] = True
    servings = float(recipe.get("servings") or 1)
    per_serving = {key: totals[key] / servings for key in NUTRIENT_KEYS}
    return {
        "total": totals,
        "per_serving": per_serving,
        "seen": seen,
        "missing": missing,
        "servings": servings,
    }


def fmt(number: float) -> str:
    rounded = round(float(number), 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.1f}".replace(".", ",")


def format_amount(amount: float, basis: str) -> str:
    unit = BASIS_LABEL.get(basis, basis)
    return f"{fmt(amount)} {unit}"


def format_kcal(nutrition: dict, per_serving: bool = True) -> str:
    bucket = "per_serving" if per_serving else "total"
    if not nutrition["seen"]["kcal"]:
        return "нет данных о калориях"
    prefix = "" if not nutrition["missing"]["kcal"] else "~"
    value = nutrition[bucket]["kcal"]
    text = f"{prefix}{fmt(value)} ккал"
    if per_serving:
        text += " на порцию"
    if nutrition["missing"]["kcal"]:
        names = ", ".join(nutrition["missing"]["kcal"])
        text += f" (нет данных: {names})"
    return text


def product_lines(products: list[dict]) -> list[str]:
    if not products:
        return ["Пока пусто."]
    lines = []
    for product in products:
        basis = product.get("basis")
        amount = format_amount(float(product.get("quantity") or 0), basis)
        bits = [f"{product.get('name')} - {amount}"]
        minimum = product.get("minQuantity")
        if minimum is not None and float(product.get("quantity") or 0) <= float(minimum):
            bits.append(f"мало (порог {format_amount(float(minimum), basis)})")
        if product.get("kcal") is not None:
            per = "1 шт" if basis == "pcs" else f"100 {BASIS_LABEL[basis]}"
            bits.append(f"{fmt(product['kcal'])} ккал / {per}")
        lines.append(", ".join(bits))
    return lines


def recipe_lines(recipes: list[dict], products_by_id: dict[str, dict]) -> list[str]:
    if not recipes:
        return ["Пока пусто."]
    lines = []
    for recipe in recipes:
        nutrition = compute_recipe_nutrition(recipe, products_by_id)
        lines.append(f"{recipe.get('name')} - {format_kcal(nutrition)}")
    return lines


def prep_lines(preps: list[dict]) -> list[str]:
    if not preps:
        return ["Пока пусто."]
    lines = []
    for prep in preps:
        left = prep.get("portionsLeft")
        total = prep.get("portionsTotal")
        text = f"{prep.get('name')} - осталось {fmt(left)} из {fmt(total)}"
        if prep.get("madeOn"):
            text += f", с {prep['madeOn']}"
        lines.append(text)
    return lines


def render_summary(data: dict) -> str:
    products_by_id = index_by_id(data["products"])
    sections = [
        ("Продукты", product_lines(data["products"])),
        ("Рецепты", recipe_lines(data["recipes"], products_by_id)),
        ("Заготовки", prep_lines(data["preps"])),
    ]
    blocks = []
    for title, lines in sections:
        blocks.append(title)
        blocks.extend(f"  {line}" for line in lines)
    return "\n".join(blocks)


def render_recipe(recipe: dict, products_by_id: dict[str, dict]) -> str:
    nutrition = compute_recipe_nutrition(recipe, products_by_id)
    lines = [
        recipe["name"],
        f"Порций: {fmt(nutrition['servings'])}",
        f"На порцию: {format_kcal(nutrition)}",
        f"На всё блюдо: {format_kcal(nutrition, per_serving=False)}",
    ]
    macro_bits = []
    for key in ("protein", "fat", "carbs"):
        if nutrition["seen"][key]:
            prefix = "" if not nutrition["missing"][key] else "~"
            macro_bits.append(f"{NUTRIENT_LABEL[key]} {prefix}{fmt(nutrition['per_serving'][key])} г")
    if macro_bits:
        lines.append("На порцию: " + ", ".join(macro_bits))
    lines.append("Ингредиенты:")
    if not recipe.get("ingredients"):
        lines.append("  нет")
    for ingredient in recipe.get("ingredients") or []:
        product = products_by_id.get(ingredient["productId"])
        name = product.get("name") if product else ingredient["productId"]
        basis = product.get("basis") if product else ""
        lines.append(f"  {name} - {format_amount(float(ingredient['amount']), basis)}")
    steps = recipe.get("steps") or []
    if steps:
        lines.append("Шаги:")
        for index, step in enumerate(steps, start=1):
            lines.append(f"  {index}. {step}")
    if recipe.get("notes"):
        lines.append(f"Заметка: {recipe['notes']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Учёт продуктов, рецептов и заготовок")
    parser.add_argument(
        "command",
        nargs="?",
        default="summary",
        choices=("summary", "products", "recipes", "preps", "recipe", "check"),
    )
    parser.add_argument("recipe_id", nargs="?")
    return parser


def main(argv: list[str] | None = None, data_dir: Path = DATA) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "recipe" and not args.recipe_id:
        print("Укажите id рецепта: python3 food.py recipe <id>", file=sys.stderr)
        return 1
    try:
        data = load_all(data_dir)
    except DataError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    errors = validate(data)
    if args.command == "check":
        if errors:
            print("\n".join(errors))
            return 1
        print("Данные в порядке.")
        return 0
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    products_by_id = index_by_id(data["products"])
    if args.command == "summary":
        print(render_summary(data))
    elif args.command == "products":
        print("\n".join(product_lines(data["products"])))
    elif args.command == "recipes":
        print("\n".join(recipe_lines(data["recipes"], products_by_id)))
    elif args.command == "preps":
        print("\n".join(prep_lines(data["preps"])))
    elif args.command == "recipe":
        recipes = index_by_id(data["recipes"])
        recipe = recipes.get(args.recipe_id)
        if recipe is None:
            print(f"Нет рецепта {args.recipe_id}", file=sys.stderr)
            return 1
        print(render_recipe(recipe, products_by_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
