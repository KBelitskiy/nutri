"""Тесты сервиса распознавания фото еды (bot.services.vision)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.vision import analyze_meal_photo


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    return client


async def test_analyze_meal_photo_returns_parsed_dict(mock_client: MagicMock) -> None:
    mock_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"description": "Греческий салат", "calories": 250, "protein_g": 8, "fat_g": 20, "carbs_g": 10}'
                    )
                )
            ]
        )
    )
    result = await analyze_meal_photo(mock_client, "gpt-4o-mini", "https://example.com/photo.jpg")
    assert result["description"] == "Греческий салат"
    assert result["calories"] == 250.0
    assert result["protein_g"] == 8.0
    assert result["fat_g"] == 20.0
    assert result["carbs_g"] == 10.0


async def test_analyze_meal_photo_handles_empty_content(mock_client: MagicMock) -> None:
    mock_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=None))])
    )
    result = await analyze_meal_photo(mock_client, "gpt-4o", "https://x.com/img.jpg")
    assert result["description"] == "Блюдо по фото"
    assert result["calories"] == 0.0


async def test_analyze_meal_photo_handles_partial_json(mock_client: MagicMock) -> None:
    mock_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"calories": 400}'))]
        )
    )
    result = await analyze_meal_photo(mock_client, "gpt-4o", "https://x.com/img.jpg")
    assert result["calories"] == 400.0
    assert result["description"] == "Блюдо по фото"
    assert result["protein_g"] == 0.0
