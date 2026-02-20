from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import crud
from bot.services.nutrition import summarize_progress


def template_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "save_meal_template",
                "description": "Сохраняет блюдо в избранные шаблоны пользователя.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "calories": {"type": "number"},
                        "protein_g": {"type": "number"},
                        "fat_g": {"type": "number"},
                        "carbs_g": {"type": "number"},
                        "meal_type": {"type": "string"},
                    },
                    "required": [
                        "telegram_id",
                        "name",
                        "description",
                        "calories",
                        "protein_g",
                        "fat_g",
                        "carbs_g",
                    ],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_meal_templates",
                "description": "Возвращает список избранных шаблонов блюд пользователя.",
                "parameters": {
                    "type": "object",
                    "properties": {"telegram_id": {"type": "integer"}},
                    "required": ["telegram_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "use_meal_template",
                "description": "Создает запись приема пищи из выбранного шаблона.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "template_id": {"type": "integer"},
                    },
                    "required": ["telegram_id", "template_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_meal_template",
                "description": "Удаляет шаблон блюда из избранного по id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "telegram_id": {"type": "integer"},
                        "template_id": {"type": "integer"},
                    },
                    "required": ["telegram_id", "template_id"],
                },
            },
        },
    ]


def template_tool_handlers(sessionmaker: async_sessionmaker) -> dict[str, Any]:
    async def save_meal_template(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            row = await crud.create_meal_template(
                session,
                telegram_id=tid,
                name=str(args["name"]),
                description=str(args["description"]),
                calories=float(args["calories"]),
                protein_g=float(args["protein_g"]),
                fat_g=float(args["fat_g"]),
                carbs_g=float(args["carbs_g"]),
                meal_type=str(args.get("meal_type", "snack")),
            )
            return {"ok": True, "template_id": row.id, "name": row.name}

    async def get_meal_templates(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        async with sessionmaker() as session:
            rows = await crud.get_meal_templates(session, tid)
            return {
                "templates": [
                    {
                        "id": x.id,
                        "name": x.name,
                        "description": x.description,
                        "calories": x.calories,
                        "protein_g": x.protein_g,
                        "fat_g": x.fat_g,
                        "carbs_g": x.carbs_g,
                        "meal_type": x.meal_type,
                        "use_count": x.use_count,
                    }
                    for x in rows
                ]
            }

    async def use_meal_template(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        template_id = int(args["template_id"])
        async with sessionmaker() as session:
            tpl = await crud.get_meal_template_by_id(session, tid, template_id)
            if tpl is None:
                return {"error": "Template not found"}
            await crud.add_meal_log(
                session=session,
                telegram_id=tid,
                description=tpl.description,
                calories=float(tpl.calories),
                protein_g=float(tpl.protein_g),
                fat_g=float(tpl.fat_g),
                carbs_g=float(tpl.carbs_g),
                meal_type=tpl.meal_type,
            )
            await crud.increment_meal_template_usage(session, tid, template_id)
            user = await crud.get_user(session, tid)
            consumed = await crud.get_meal_summary_for_day(session, tid)
            result: dict[str, Any] = {"ok": True, "template_id": template_id, "name": tpl.name}
            if user is not None:
                targets = {
                    "daily_calories_target": user.daily_calories_target,
                    "daily_protein_target": user.daily_protein_target,
                    "daily_fat_target": user.daily_fat_target,
                    "daily_carbs_target": user.daily_carbs_target,
                }
                progress = summarize_progress(consumed, targets)
                result["daily_summary"] = {
                    "consumed": consumed,
                    "targets": targets,
                    "progress": progress,
                }
            return result

    async def delete_meal_template(args: dict[str, Any]) -> dict[str, Any]:
        tid = int(args["telegram_id"])
        template_id = int(args["template_id"])
        async with sessionmaker() as session:
            ok = await crud.delete_meal_template(session, tid, template_id)
            return {"ok": ok}

    return {
        "save_meal_template": save_meal_template,
        "get_meal_templates": get_meal_templates,
        "use_meal_template": use_meal_template,
        "delete_meal_template": delete_meal_template,
    }
