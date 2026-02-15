"""Тесты AI-агента (bot.services.ai_agent)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.ai_agent import AIAgent


@pytest.fixture
def mock_openai_client() -> MagicMock:
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    return client


def test_register_tools_stores_schema_and_handlers() -> None:
    agent = AIAgent(api_key="sk-fake", model="gpt-4o-mini")
    schema = [{"type": "function", "function": {"name": "add_meal"}}]
    handlers = {"add_meal": AsyncMock(return_value={"ok": True})}
    agent.register_tools(schema, handlers)
    assert agent._tools_schema == schema
    assert agent._tool_handlers == handlers


async def test_ask_without_tools_returns_message_content(mock_openai_client: MagicMock) -> None:
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Привет! Чем помочь?"))]
        )
    )
    agent = AIAgent(api_key="sk-fake", model="gpt-4o-mini")
    agent.client = mock_openai_client
    reply = await agent.ask("Привет", use_tools=False)
    assert reply == "Привет! Чем помочь?"


async def test_ask_without_tools_returns_fallback_on_empty_content(mock_openai_client: MagicMock) -> None:
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=None))])
    )
    agent = AIAgent(api_key="sk-fake", model="gpt-4o-mini")
    agent.client = mock_openai_client
    reply = await agent.ask("Хелло", use_tools=False)
    assert "Не удалось" in reply or "Готово" in reply or reply


async def test_parse_meal_text_returns_parsed_dict(mock_openai_client: MagicMock) -> None:
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"description": "Овсянка 200 г", "calories": 150, "protein_g": 5, "fat_g": 3, "carbs_g": 27, "meal_type": "breakfast"}'
                    )
                )
            ]
        )
    )
    agent = AIAgent(api_key="sk-fake", model="gpt-4o-mini")
    agent.client = mock_openai_client
    result = await agent.parse_meal_text("овсянка 200 грамм")
    assert result["description"] == "Овсянка 200 г"
    assert result["calories"] == 150.0
    assert result["meal_type"] == "breakfast"


async def test_parse_meal_text_fallback_description(mock_openai_client: MagicMock) -> None:
    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"calories": 100}'))]
        )
    )
    agent = AIAgent(api_key="sk-fake", model="gpt-4o-mini")
    agent.client = mock_openai_client
    result = await agent.parse_meal_text("что-то съел")
    assert result["description"] == "что-то съел"
    assert result["meal_type"] == "snack"
