import json
from pathlib import Path

from app.services.reply_composer import render_template

FOODS = json.loads(
    (Path(__file__).resolve().parents[3] / "seed" / "foods_andhra.json").read_text()
)["foods"]


def permitted(food: dict, conditions: list[str]) -> bool:
    return all(
        food.get(field) in {"prefer", "ok"}
        for condition, field in (
            ("diabetes", "dm_suitability"),
            ("hypertension", "htn_suitability"),
        )
        if condition in conditions
    )


def daily_tip(conditions: list[str], language: str, recent: list[str] | None = None) -> dict | None:
    candidates = [
        food
        for food in FOODS
        if permitted(food, conditions)
        and food["id"] not in (recent or [])
        and all(
            food.get(field) == "prefer"
            for condition, field in (
                ("diabetes", "dm_suitability"),
                ("hypertension", "htn_suitability"),
            )
            if condition in conditions
        )
    ]
    if not candidates:
        return None
    food = candidates[0]
    values = {"prefer_food": food["names"][language]}
    return {
        "template_key": "nutrition_tip_add",
        "params": values,
        "food_ids": [food["id"]],
        "text": render_template("nutrition_tip_add", language, values),
    }


def meal_feedback(raw: str, conditions: list[str], language: str) -> dict | None:
    matched = [
        food
        for food in FOODS
        if any(alias.casefold() in raw.casefold() for alias in food["aliases"])
    ]
    if not matched:
        return None
    good = [food for food in matched if permitted(food, conditions)]
    limited = [food for food in matched if not permitted(food, conditions)]
    if limited:
        return daily_tip(conditions, language)
    foods = good
    key = "meal_feedback_good"
    params = {"foods": ", ".join(food["names"][language] for food in foods)}
    return {"template_key": key, "params": params, "food_ids": [food["id"] for food in foods]}
