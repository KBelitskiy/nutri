from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from openai import AsyncOpenAI

from bot.prompts import AGENT_SYSTEM, MEAL_PARSE


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class AIAgent:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self._tools_schema: list[dict[str, Any]] = []
        self._tool_handlers: dict[str, ToolHandler] = {}

    def register_tools(
        self, tools_schema: list[dict[str, Any]], handlers: dict[str, ToolHandler]
    ) -> None:
        self._tools_schema = tools_schema
        self._tool_handlers = handlers

    async def ask(
        self,
        user_text: str,
        context: str | None = None,
        *,
        use_tools: bool = True,
        history: list[tuple[str, str]] | None = None,
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "system", "content": AGENT_SYSTEM}]
        if context:
            messages.append({"role": "system", "content": f"Контекст: {context}"})
        if history:
            for user_msg, assistant_msg in history:
                messages.append({"role": "user", "content": user_msg})
                messages.append({"role": "assistant", "content": assistant_msg})
        messages.append({"role": "user", "content": user_text})

        if not use_tools or not self._tools_schema:
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=0.4
            )
            return response.choices[0].message.content or "Не удалось сформировать ответ."

        while True:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self._tools_schema,
                tool_choice="auto",
                temperature=0.3,
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return msg.content or "Готово."

            messages.append(msg.model_dump())
            for call in msg.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                handler = self._tool_handlers.get(name)
                if handler is None:
                    result = {"error": f"Unknown tool: {name}"}
                else:
                    try:
                        result = await handler(args)
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": str(exc)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

    async def parse_meal_text(self, text: str) -> dict[str, float | str]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": MEAL_PARSE},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return {
            "description": str(parsed.get("description", text)),
            "calories": float(parsed.get("calories", 0.0)),
            "protein_g": float(parsed.get("protein_g", 0.0)),
            "fat_g": float(parsed.get("fat_g", 0.0)),
            "carbs_g": float(parsed.get("carbs_g", 0.0)),
            "meal_type": str(parsed.get("meal_type", "snack")),
        }

