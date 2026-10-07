import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from food import (
    compute_recipe_nutrition,
    food_kcal,
    index_by_id,
    load_all,
    load_menu,
    main,
    scale_nutrient,
    validate,
    validate_menu,
)


OATS = {
    "id": "oats",
    "name": "Овсянка",
    "basis": "g",
    "quantity": 500,
    "kcal": 379,
    "protein": 13.5,
    "fat": 6.2,
    "carbs": 67.7,
}
MILK = {
    "id": "milk",
    "name": "Молоко",
    "basis": "ml",
    "quantity": 900,
    "kcal": 60,
    "protein": 3,
    "fat": 3.2,
    "carbs": 4.7,
}
EGG = {
    "id": "egg",
    "name": "Яйцо",
    "basis": "pcs",
    "quantity": 6,
    "kcal": 155,
    "protein": 13,
    "fat": 11,
    "carbs": 1.1,
}
SALT = {
    "id": "salt",
    "name": "Соль",
    "basis": "g",
    "quantity": 100,
    "kcal": None,
}


def products_by_id(*items):
    return {item["id"]: item for item in items}


class NutritionTests(unittest.TestCase):
    def test_grams_and_milliliters_per_serving(self):
        recipe = {
            "id": "oatmeal",
            "name": "Овсянка",
            "servings": 2,
            "ingredients": [
                {"productId": "oats", "amount": 100},
                {"productId": "milk", "amount": 200},
            ],
        }
        nutrition = compute_recipe_nutrition(recipe, products_by_id(OATS, MILK))
        self.assertAlmostEqual(nutrition["total"]["kcal"], 499.0)
        self.assertAlmostEqual(nutrition["per_serving"]["kcal"], 249.5)
        self.assertAlmostEqual(nutrition["total"]["protein"], 19.5)
        self.assertEqual(nutrition["missing"]["kcal"], [])
        self.assertTrue(nutrition["seen"]["kcal"])

    def test_pieces(self):
        self.assertAlmostEqual(scale_nutrient(EGG, 2, "kcal"), 310.0)
        recipe = {
            "id": "eggs",
            "servings": 1,
            "ingredients": [{"productId": "egg", "amount": 2}],
        }
        nutrition = compute_recipe_nutrition(recipe, products_by_id(EGG))
        self.assertAlmostEqual(nutrition["total"]["protein"], 26.0)

    def test_missing_kcal_keeps_partial_sum(self):
        recipe = {
            "id": "oatmeal",
            "servings": 1,
            "ingredients": [
                {"productId": "oats", "amount": 100},
                {"productId": "salt", "amount": 1},
            ],
        }
        nutrition = compute_recipe_nutrition(recipe, products_by_id(OATS, SALT))
        self.assertAlmostEqual(nutrition["total"]["kcal"], 379.0)
        self.assertEqual(nutrition["missing"]["kcal"], ["Соль"])
        self.assertTrue(nutrition["seen"]["kcal"])


class ValidateTests(unittest.TestCase):
    def test_empty_repo_data_is_valid(self):
        data = load_all(Path(__file__).resolve().parent / "data")
        self.assertEqual(validate(data), [])

    def test_unknown_quantity_is_valid(self):
        data = {
            "products": [
                {
                    "id": "salt",
                    "name": "Соль",
                    "basis": "g",
                    "quantity": None,
                    "kcal": 0,
                    "protein": 0,
                    "fat": 0,
                    "carbs": 0,
                }
            ],
            "recipes": [],
            "preps": [],
        }
        self.assertEqual(validate(data), [])

    def test_unknown_product_and_duplicate_id(self):
        data = {
            "products": [OATS, dict(OATS)],
            "recipes": [
                {
                    "id": "bad",
                    "name": "Пусто",
                    "servings": 1,
                    "ingredients": [{"productId": "nope", "amount": 1}],
                }
            ],
            "preps": [],
        }
        errors = validate(data)
        self.assertTrue(any("повтор id oats" in error for error in errors))
        self.assertTrue(any("нет продукта nope" in error for error in errors))

    def test_prep_date_and_recipe_link(self):
        data = {
            "products": [],
            "recipes": [],
            "preps": [
                {
                    "id": "soup",
                    "name": "Суп",
                    "portionsTotal": 4,
                    "portionsLeft": 4,
                    "recipeId": "missing",
                    "madeOn": "07.10.2026",
                }
            ],
        }
        errors = validate(data)
        self.assertTrue(any("нет рецепта missing" in error for error in errors))
        self.assertTrue(any("madeOn" in error for error in errors))


class WaffleRecipeTests(unittest.TestCase):
    def test_saved_waffle_recipe(self):
        data = load_all(Path(__file__).resolve().parent / "data")
        self.assertEqual(validate(data), [])
        recipe = index_by_id(data["recipes"])["belgian-waffles"]
        nutrition = compute_recipe_nutrition(recipe, index_by_id(data["products"]))
        self.assertAlmostEqual(nutrition["servings"], 6.5)
        self.assertAlmostEqual(nutrition["per_serving"]["kcal"], 2334.75 / 6.5, places=2)
        self.assertEqual(nutrition["missing"]["kcal"], [])

        summary = io.StringIO()
        with redirect_stdout(summary):
            code = main(["recipe", "belgian-waffles"])
        self.assertEqual(code, 0)
        text = summary.getvalue()
        self.assertIn("Молоко 3,2% - 200 мл", text)
        self.assertIn("Разрыхлитель - 5 г (1 ч. л.)", text)
        self.assertIn("359,2 ккал на порцию", text)
        self.assertIn("13 вафель", text)


class MenuTests(unittest.TestCase):
    def test_menu_targets_and_fish_allergy(self):
        root = Path(__file__).resolve().parent
        data = load_all(root / "data")
        menu = load_menu(root / "data")
        self.assertEqual(validate_menu(menu, data), [])

        totals = {}
        meals_by_day = {}
        for day in menu["days"]:
            meals_by_day[day["date"]] = [meal["name"] for meal in day["meals"]]
            totals[day["date"]] = {person["id"]: 0.0 for person in menu["people"]}
            for meal in day["meals"]:
                for serving in meal["servings"]:
                    food = menu["foods"][serving["food"]]
                    if serving["person"] == "lesha":
                        self.assertFalse(food.get("fish"))
                    totals[day["date"]][serving["person"]] += food_kcal(food, serving)

        self.assertEqual(meals_by_day["2026-10-07"], ["Обед", "Ужин"])
        self.assertEqual(meals_by_day["2026-10-08"], ["Завтрак", "Обед", "Ужин", "Перекус"])
        self.assertEqual(meals_by_day["2026-10-09"], ["Завтрак", "Обед", "Ужин", "Перекус"])
        self.assertGreaterEqual(totals["2026-10-08"]["me"], 1600)
        self.assertLessEqual(totals["2026-10-08"]["me"], 1700)
        self.assertGreaterEqual(totals["2026-10-09"]["me"], 1450)
        self.assertLessEqual(totals["2026-10-09"]["me"], 1550)
        for date in ("2026-10-08", "2026-10-09"):
            self.assertGreaterEqual(totals[date]["lesha"], 2450)
            self.assertLessEqual(totals[date]["lesha"], 2550)
        self.assertLess(totals["2026-10-07"]["me"], 1300)
        self.assertLess(totals["2026-10-07"]["lesha"], 1900)

        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["menu"])
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("Обед: тебе филе форели 150 г", text)
        self.assertIn("Леше 1 фаршированный перец", text)
        self.assertIn("Завтрак: тебе 2 сырника", text)
        self.assertIn("рыбу нельзя", text)
        self.assertIn("1500 ккал, в день тренировки 1650", text)
        self.assertIn("цель на день 1650", text)
        self.assertIn("цель на день 1500", text)


class PrepStockTests(unittest.TestCase):
    def test_saved_prep_stock(self):
        summary = io.StringIO()
        with redirect_stdout(summary):
            code = main(["preps"])
        self.assertEqual(code, 0)
        text = summary.getvalue()
        self.assertIn("Драники - 10 шт", text)
        self.assertIn("Котлеты говяжьи - 22 шт по 100 г, 5 пачек по 4 и 1 пачка по 2", text)
        self.assertIn("Сырники - 36 шт, 6 пачек по 6", text)
        self.assertIn("Куриные котлеты в панко - 16 шт по 100 г, 4 пачки по 4", text)
        self.assertIn("Фаршированные перцы - 7 шт", text)


class CliTests(unittest.TestCase):
    def test_summary_of_sample_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "products.json").write_text(
                """
                {"products": [
                  {"id": "oats", "name": "Овсянка", "basis": "g", "quantity": 80, "minQuantity": 200, "kcal": 379,
                   "protein": 13.5, "fat": 6.2, "carbs": 67.7}
                ]}
                """,
                encoding="utf-8",
            )
            (root / "recipes.json").write_text(
                """
                {"recipes": [
                  {"id": "oatmeal", "name": "Овсянка", "servings": 1,
                   "ingredients": [{"productId": "oats", "amount": 50}],
                   "steps": ["Залить кипятком"]}
                ]}
                """,
                encoding="utf-8",
            )
            (root / "preps.json").write_text(
                """
                {"preps": [
                  {"id": "batch", "name": "Овсянка", "recipeId": "oatmeal",
                   "portionsTotal": 3, "portionsLeft": 2, "madeOn": "2026-10-07"}
                ]}
                """,
                encoding="utf-8",
            )
            summary = io.StringIO()
            with redirect_stdout(summary):
                code = main(["summary"], root)
            self.assertEqual(code, 0)
            text = summary.getvalue()
            self.assertIn("Овсянка - 80 г, мало (порог 200 г), 379 ккал / 100 г", text)
            self.assertIn("Овсянка - 189,5 ккал на порцию", text)
            self.assertIn("Овсянка - осталось 2 из 3, с 2026-10-07", text)

            detail = io.StringIO()
            with redirect_stdout(detail):
                code = main(["recipe", "oatmeal"], root)
            self.assertEqual(code, 0)
            self.assertIn("1. Залить кипятком", detail.getvalue())

            check = io.StringIO()
            with redirect_stdout(check):
                code = main(["check"], root)
            self.assertEqual(code, 0)
            self.assertIn("Данные в порядке.", check.getvalue())


if __name__ == "__main__":
    unittest.main()
