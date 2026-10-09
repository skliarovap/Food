# Еда

Список продуктов, рецепты, заготовки и калории. Данные лежат в JSON, сводка считается скриптом.

## Файлы

- `data/products.json` - что есть дома и пищевая ценность
- `data/recipes.json` - сохранённые рецепты
- `data/preps.json` - заготовки и сколько порций осталось
- `data/menu.json` - меню и порции на двоих

Калории продукта задаются на 100 г, на 100 мл или на 1 штуку. В рецепте количество указано в тех же единицах: граммы, миллилитры или штуки.

## Сводка

```bash
python3 food.py
python3 food.py products
python3 food.py recipes
python3 food.py preps
python3 food.py recipe <id>
python3 food.py menu
python3 food.py check
```

Если у части ингредиентов нет калорий, в сводке будет приблизительное число и список продуктов без данных.

## Продукт

```json
{
  "id": "oats",
  "name": "Овсянка",
  "category": "крупы",
  "basis": "g",
  "quantity": 500,
  "minQuantity": 200,
  "kcal": 379,
  "protein": 13.5,
  "fat": 6.2,
  "carbs": 67.7,
  "notes": ""
}
```

`basis`: `g` (граммы), `ml` (миллилитры) или `pcs` (штуки). `kcal`, `protein`, `fat`, `carbs` можно оставить `null`, пока нет цифр. `quantity` тоже можно оставить `null`, если запас ещё не считали. `minQuantity` необязателен: если запас известен и не выше порога, сводка помечает продукт как «мало».

## Рецепт

```json
{
  "id": "oatmeal",
  "name": "Овсянка",
  "servings": 1,
  "ingredients": [
    { "productId": "oats", "amount": 50 }
  ],
  "steps": ["Залить кипятком и подождать 5 минут"],
  "tags": ["завтрак"],
  "notes": ""
}
```

`productId` должен совпадать с `id` продукта. `amount` для `g` и `ml` - это граммы и миллилитры, для `pcs` - число штук.

## Заготовка

```json
{
  "id": "oatmeal-batch",
  "name": "Овсянка",
  "recipeId": "oatmeal",
  "portionsTotal": 4,
  "portionsLeft": 3,
  "madeOn": "2026-10-07",
  "notes": ""
}
```

`recipeId`, `madeOn`, `portionsTotal`, `packSize`, `packs` и `pieceWeightG` необязательны. Если исходный размер партии неизвестен, `portionsTotal` можно не писать: в сводке будет только то, сколько есть сейчас. `packSize` - штук в одинаковых пачках. Если пачки разного размера, вместо этого пиши `packs`: список объектов `count` и `size`. Сумма пачек должна совпадать с `portionsLeft`. `pieceWeightG` - вес одной штуки в граммах. Дата в формате `ГГГГ-ММ-ДД`.
