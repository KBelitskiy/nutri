"""CLI для оценки КБЖУ по фото.

Использование:
    python -m estimator photo.jpg
    python -m estimator photo.jpg --caption "200г курицы с рисом"
    python -m estimator photo.jpg --model gpt-4o
    python -m estimator https://example.com/food.jpg
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from estimator.core import analyze_meal_photo


def _to_image_url(source: str) -> str:
    """Превратить локальный путь или URL в image_url для API."""
    if source.startswith(("http://", "https://", "data:")):
        return source
    path = Path(source).expanduser()
    if not path.exists():
        print(f"Файл не найден: {path}", file=sys.stderr)
        sys.exit(1)
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


async def _run(source: str, model: str, caption: str | None) -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = (
        os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("BASE_URL", "").strip()
        or os.getenv("base_url", "").strip()
        or None
    )
    if not api_key:
        print("OPENAI_API_KEY не задан", file=sys.stderr)
        sys.exit(1)

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    image_url = _to_image_url(source)

    result = await analyze_meal_photo(client, model, image_url, caption=caption)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Оценка КБЖУ по фото еды",
    )
    parser.add_argument(
        "image",
        help="Путь к файлу или URL изображения",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Модель (по умолчанию из OPENAI_MODEL_VISION или gpt-4o-mini)",
    )
    parser.add_argument(
        "--caption",
        default=None,
        help="Подпись к фото (граммовки, название блюда)",
    )
    args = parser.parse_args()

    if args.model is None:
        load_dotenv()
        args.model = os.getenv("OPENAI_MODEL_VISION", "gpt-4o-mini")

    asyncio.run(_run(args.image, args.model, args.caption))


if __name__ == "__main__":
    main()
