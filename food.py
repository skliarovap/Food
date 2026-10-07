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
        if product.get("quantity") is None:
            quantity = None
        else:
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
        if prep.get("portionsTotal") is None:
            total = None
        else:
            total = _as_number(prep.get("portionsTotal"), f"{label}.portionsTotal", errors)
        left = _as_number(prep.get("portionsLeft"), f"{label}.portionsLeft", errors)
        if total is not None and total <= 0:
            errors.append(f"{label}: portionsTotal должен быть больше нуля")
        if left is not None and left < 0:
            errors.append(f"{label}: portionsLeft не может быть отрицательным")
        if total is not None and left is not None and left > total:
            errors.append(f"{label}: portionsLeft больше portionsTotal")
        for key in ("packSize", "pieceWeightG"):
            if prep.get(key) is None:
                continue
            value = _as_number(prep.get(key), f"{label}.{key}", errors)
            if value is not None and value <= 0:
                errors.append(f"{label}: {key} должен быть больше нуля")
        packed = _validate_packs(prep, label, errors)
        if packed is not None and left is not None and abs(packed - left) > 1e-9:
            errors.append(f"{label}: в пачках {fmt(packed)} шт, а portionsLeft равен {fmt(left)}")
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
        quantity = product.get("quantity")
        if quantity is None:
            amount = "количество не указано"
        else:
            amount = format_amount(float(quantity), basis)
        bits = [f"{product.get('name')} - {amount}"]
        minimum = product.get("minQuantity")
        if minimum is not None and quantity is not None and float(quantity) <= float(minimum):
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


def _validate_packs(prep: dict, label: str, errors: list[str]) -> float | None:
    packs = prep.get("packs")
    if packs is None:
        return None
    if prep.get("packSize") is not None:
        errors.append(f"{label}: укажи packs или packSize")
    if not isinstance(packs, list) or not packs:
        errors.append(f"{label}: packs должен быть непустым списком")
        return None
    total = 0.0
    complete = True
    for index, group in enumerate(packs, start=1):
        group_label = f"{label}, пачки #{index}"
        if not isinstance(group, dict):
            errors.append(f"{group_label}: ожидался объект")
            complete = False
            continue
        count = _as_number(group.get("count"), f"{group_label}.count", errors)
        size = _as_number(group.get("size"), f"{group_label}.size", errors)
        if count is not None and count <= 0:
            errors.append(f"{group_label}: count должен быть больше нуля")
        if size is not None and size <= 0:
            errors.append(f"{group_label}: size должен быть больше нуля")
        if count is None or size is None or count <= 0 or size <= 0:
            complete = False
            continue
        total += count * size
    if not complete:
        return None
    return total


def pack_word(count: int) -> str:
    number = abs(count) % 100
    if 11 <= number <= 14:
        return "пачек"
    last = number % 10
    if last == 1:
        return "пачка"
    if 2 <= last <= 4:
        return "пачки"
    return "пачек"


def format_pack_text(prep: dict, left) -> str:
    groups = prep.get("packs")
    if isinstance(groups, list) and groups:
        parts = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            count = int(round(float(group["count"])))
            parts.append(f"{fmt(count)} {pack_word(count)} по {fmt(group['size'])}")
        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + " и " + parts[-1]
    pack = prep.get("packSize")
    if pack is None or left is None or float(pack) <= 0:
        return ""
    packs = float(left) / float(pack)
    if abs(packs - round(packs)) < 1e-9:
        pack_count = int(round(packs))
        return f"{fmt(pack_count)} {pack_word(pack_count)} по {fmt(pack)}"
    return f"в пачке по {fmt(pack)}"


def prep_lines(preps: list[dict]) -> list[str]:
    if not preps:
        return ["Пока пусто."]
    lines = []
    for prep in preps:
        left = prep.get("portionsLeft")
        total = prep.get("portionsTotal")
        if total is None:
            text = f"{prep.get('name')} - {fmt(left)} шт"
        else:
            text = f"{prep.get('name')} - осталось {fmt(left)} из {fmt(total)}"
        if prep.get("pieceWeightG") is not None:
            text += f" по {fmt(prep['pieceWeightG'])} г"
        pack_text = format_pack_text(prep, left)
        if pack_text:
            text += f", {pack_text}"
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
        format_kcal(nutrition),
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
        line = f"  {name} - {format_amount(float(ingredient['amount']), basis)}"
        if ingredient.get("note"):
            line += f" ({ingredient['note']})"
        lines.append(line)
    steps = recipe.get("steps") or []
    if steps:
        lines.append("Шаги:")
        for index, step in enumerate(steps, start=1):
            lines.append(f"  {index}. {step}")
    if recipe.get("notes"):
        lines.append(f"Заметка: {recipe['notes']}")
    return "\n".join(lines)


def load_menu(data_dir: Path = DATA) -> dict:
    return load_json(data_dir / "menu.json")


def food_kcal(food: dict, serving: dict) -> float:
    if food.get("kcalPerPiece") is not None:
        return float(food["kcalPerPiece"]) * float(serving["pieces"])
    amount = serving.get("grams", serving.get("ml"))
    return float(food["kcalPer100"]) * float(amount) / 100.0


def serving_amount_text(serving: dict) -> str:
    if serving.get("pieces") is not None:
        return f"{fmt(serving['pieces'])} шт"
    if serving.get("ml") is not None:
        return f"{fmt(serving['ml'])} мл"
    return f"{fmt(serving['grams'])} г"


def planned_prep_use(menu: dict) -> dict[str, float]:
    used: dict[str, float] = {}
    foods = menu.get("foods") or {}
    for day in menu.get("days") or []:
        for meal in day.get("meals") or []:
            for serving in meal.get("servings") or []:
                food = foods.get(serving.get("food"))
                prep_id = food.get("prepId") if isinstance(food, dict) else None
                if not prep_id or serving.get("pieces") is None:
                    continue
                used[prep_id] = used.get(prep_id, 0.0) + float(serving["pieces"])
    return used


def validate_menu(menu: dict, data: dict | None = None) -> list[str]:
    errors: list[str] = []
    people = menu.get("people")
    foods = menu.get("foods")
    days = menu.get("days")
    if not isinstance(people, list) or not people:
        return ["menu.people: ожидался непустой список"]
    if not isinstance(foods, dict):
        return ["menu.foods: ожидался объект"]
    if not isinstance(days, list) or not days:
        return ["menu.days: ожидался непустой список"]

    people_by_id: dict[str, dict] = {}
    for index, person in enumerate(people, start=1):
        if not isinstance(person, dict):
            errors.append(f"menu, человек #{index}: ожидался объект")
            continue
        person_id = _require_str(person, "id", f"menu, человек #{index}", errors)
        _require_str(person, "name", f"menu, человек {person_id or index}", errors)
        target = _as_number(person.get("kcalTarget"), f"menu, человек {person_id or index}.kcalTarget", errors)
        if target is not None and target <= 0:
            errors.append(f"menu, человек {person_id}: kcalTarget должен быть больше нуля")
        if person.get("trainingKcalTarget") is not None:
            training_target = _as_number(
                person.get("trainingKcalTarget"),
                f"menu, человек {person_id or index}.trainingKcalTarget",
                errors,
            )
            if training_target is not None and training_target <= 0:
                errors.append(f"menu, человек {person_id}: trainingKcalTarget должен быть больше нуля")
        if person_id:
            if person_id in people_by_id:
                errors.append(f"menu: повтор id {person_id}")
            people_by_id[person_id] = person

    for food_id, food in foods.items():
        if not isinstance(food, dict):
            errors.append(f"menu, продукт {food_id}: ожидался объект")
            continue
        _require_str(food, "name", f"menu, продукт {food_id}", errors)
        per_piece = food.get("kcalPerPiece")
        per_100 = food.get("kcalPer100")
        if per_piece is None and per_100 is None:
            errors.append(f"menu, продукт {food_id}: нужна калорийность")
        if per_piece is not None and per_piece <= 0:
            errors.append(f"menu, продукт {food_id}: kcalPerPiece должен быть больше нуля")
        if per_100 is not None and per_100 < 0:
            errors.append(f"menu, продукт {food_id}: kcalPer100 не может быть отрицательным")

    preps = index_by_id(data["preps"]) if data else {}
    for day in days:
        if not isinstance(day, dict):
            errors.append("menu: день должен быть объектом")
            continue
        label = f"menu, {day.get('title') or day.get('date') or 'день'}"
        _require_str(day, "date", label, errors)
        _require_str(day, "title", label, errors)
        training = day.get("training") or []
        if not isinstance(training, list):
            errors.append(f"{label}: training должен быть списком")
        else:
            for person_id in training:
                if person_id not in people_by_id:
                    errors.append(f"{label}: в тренировке нет человека {person_id}")
        for meal in day.get("meals") or []:
            if not isinstance(meal, dict):
                errors.append(f"{label}: приём пищи должен быть объектом")
                continue
            meal_label = f"{label}, {meal.get('name') or 'приём'}"
            for index, serving in enumerate(meal.get("servings") or [], start=1):
                serving_label = f"{meal_label}, порция #{index}"
                if not isinstance(serving, dict):
                    errors.append(f"{serving_label}: ожидался объект")
                    continue
                person_id = serving.get("person")
                person = people_by_id.get(person_id)
                if person is None:
                    errors.append(f"{serving_label}: нет человека {person_id}")
                food = foods.get(serving.get("food"))
                if not isinstance(food, dict):
                    errors.append(f"{serving_label}: нет продукта {serving.get('food')}")
                    continue
                has_pieces = serving.get("pieces") is not None
                has_amount = serving.get("grams") is not None or serving.get("ml") is not None
                if food.get("kcalPerPiece") is not None and not has_pieces:
                    errors.append(f"{serving_label}: нужны штуки")
                if food.get("kcalPerPiece") is None and not has_amount:
                    errors.append(f"{serving_label}: нужны граммы или миллилитры")
                if person and food.get("fish") and "fish" in person.get("allergies", []):
                    errors.append(f"{serving_label}: {person.get('name')} нельзя рыбу")
                prep_id = food.get("prepId")
                if prep_id and data is not None and prep_id not in preps:
                    errors.append(f"{serving_label}: нет заготовки {prep_id}")

    if data is not None:
        preps = index_by_id(data["preps"])
        for prep_id, count in planned_prep_use(menu).items():
            prep = preps.get(prep_id)
            if prep is None:
                continue
            left = prep.get("portionsLeft")
            if left is not None and count - float(left) > 1e-9:
                errors.append(
                    f"menu: {prep.get('name')} в меню {fmt(count)} шт, в запасе {fmt(left)}"
                )
    return errors


MONTHS = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def cap_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def ru_plural(count: int, forms: list[str]) -> str:
    number = abs(count) % 100
    if 11 <= number <= 14:
        word = forms[2]
    else:
        last = abs(count) % 10
        if last == 1:
            word = forms[0]
        elif 2 <= last <= 4:
            word = forms[1]
        else:
            word = forms[2]
    return f"{count} {word}"


def menu_item_text(food: dict, serving: dict) -> str:
    if serving.get("pieces") is not None:
        forms = food.get("plural")
        count = int(round(float(serving["pieces"])))
        if isinstance(forms, list) and len(forms) == 3:
            return ru_plural(count, forms)
        label = food.get("short") or food["name"]
        return f"{label} {fmt(serving['pieces'])} шт"
    label = food.get("short") or food["name"]
    if serving.get("ml") is not None:
        return f"{label} {fmt(serving['ml'])} мл"
    return f"{label} {fmt(serving['grams'])} г"


def format_menu_day(day: dict) -> str:
    year, month, day_num = day["date"].split("-")
    del year
    return f"{day['title']}, {int(day_num)} {MONTHS[int(month)]}"


def person_day_target(person: dict, day: dict) -> float:
    if person["id"] in (day.get("training") or []) and person.get("trainingKcalTarget") is not None:
        return float(person["trainingKcalTarget"])
    return float(person["kcalTarget"])


def render_menu(menu: dict, preps: list[dict] | None = None) -> str:
    lines = []
    for person in menu["people"]:
        label = cap_first(person.get("menuLabel") or person["name"])
        extra = ", рыбу нельзя" if "fish" in person.get("allergies", []) else ""
        line = f"{label}: {fmt(person['kcalTarget'])} ккал{extra}"
        if person.get("trainingKcalTarget") is not None:
            line += f", в день тренировки {fmt(person['trainingKcalTarget'])}"
        lines.append(line)
    if menu.get("note"):
        lines.append(menu["note"])

    for day in menu["days"]:
        lines.append("")
        lines.append(format_menu_day(day))
        if day.get("note"):
            lines.append(day["note"])
        day_kcal = {person["id"]: 0.0 for person in menu["people"]}
        day_estimated = {person["id"]: False for person in menu["people"]}
        for meal in day["meals"]:
            grouped: dict[str, list[dict]] = {}
            for serving in meal["servings"]:
                grouped.setdefault(serving["person"], []).append(serving)
            clauses = []
            for person in menu["people"]:
                servings = grouped.get(person["id"])
                if not servings:
                    continue
                bits = []
                for serving in servings:
                    food = menu["foods"][serving["food"]]
                    day_kcal[person["id"]] += food_kcal(food, serving)
                    day_estimated[person["id"]] = day_estimated[person["id"]] or bool(food.get("estimated"))
                    bits.append(menu_item_text(food, serving))
                label = person.get("menuLabel") or person["name"]
                clauses.append(f"{label} {', '.join(bits)}")
            lines.append(f"{meal['name']}: {'. '.join(clauses)}.")
            if meal.get("note"):
                lines.append(meal["note"])
        totals = []
        for person in menu["people"]:
            mark = "~" if day_estimated[person["id"]] else ""
            label = person.get("menuLabel") or person["name"]
            totals.append(
                f"{label} {mark}{fmt(day_kcal[person['id']])} ккал, цель на день {fmt(person_day_target(person, day))}"
            )
        lines.append(f"Итого: {'. '.join(totals)}.")

    if preps is not None:
        prep_by_id = index_by_id(preps)
        parts = []
        for prep_id, count in planned_prep_use(menu).items():
            prep = prep_by_id.get(prep_id, {})
            left = prep.get("portionsLeft")
            name = prep.get("name", prep_id)
            if left is None:
                parts.append(f"{name} {fmt(count)} шт")
            else:
                parts.append(f"{name} {fmt(count)} шт, останется {fmt(float(left) - count)}")
        if parts:
            lines.append("")
            lines.append("Из заготовок уйдёт: " + "; ".join(parts) + ".")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Учёт продуктов, рецептов и заготовок")
    parser.add_argument(
        "command",
        nargs="?",
        default="summary",
        choices=("summary", "products", "recipes", "preps", "recipe", "menu", "check"),
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
    menu = None
    menu_path = data_dir / "menu.json"
    if menu_path.exists():
        try:
            menu = load_menu(data_dir)
        except DataError as exc:
            errors.append(str(exc))
        else:
            errors.extend(validate_menu(menu, data))
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
    elif args.command == "menu":
        if menu is None:
            print("Нет файла menu.json", file=sys.stderr)
            return 1
        print(render_menu(menu, data["preps"]))
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
