from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from openai import AsyncOpenAI

from bot.prompts import AGENT_SYSTEM, MEAL_PARSE

logger = logging.getLogger(__name__)

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class AIAgent:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
        vision_model: str | None = None,
    ):
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)
        self.model = model
        self.vision_model = vision_model or model
        self._tools_schema: list[dict[str, Any]] = []
        self._tool_handlers: dict[str, ToolHandler] = {}

    def register_tools(
        self, tools_schema: list[dict[str, Any]], handlers: dict[str, ToolHandler]
    ) -> None:
        self._tools_schema = tools_schema
        self._tool_handlers = handlers

    @staticmethod
    def _build_user_content(
        text: str, image_urls: list[str] | None = None
    ) -> str | list[dict[str, Any]]:
        if not image_urls:
            return text
        parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for url in image_urls:
            parts.append({"type": "image_url", "image_url": {"url": url}})
        return parts

    async def ask(
        self,
        user_text: str,
        context: str | None = None,
        *,
        use_tools: bool = True,
        history: list[tuple[str, str]] | None = None,
        image_urls: list[str] | None = None,
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "system", "content": AGENT_SYSTEM}]
        if context:
            messages.append({"role": "system", "content": f"Контекст:\n{context}"})
        if history:
            for user_msg, assistant_msg in history:
                messages.append({"role": "user", "content": user_msg})
                messages.append({"role": "assistant", "content": assistant_msg})

        user_content = self._build_user_content(user_text, image_urls)
        messages.append({"role": "user", "content": user_content})

        model = self.vision_model if image_urls else self.model

        if not use_tools or not self._tools_schema:
            response = await self.client.chat.completions.create(
                model=model, messages=messages, temperature=0.4
            )
            return response.choices[0].message.content or "Не удалось сформировать ответ."

        while True:
            response = await self.client.chat.completions.create(
                model=model,
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
                        logger.exception("Tool %s failed", name)
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

