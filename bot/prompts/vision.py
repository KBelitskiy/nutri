"""Промпты vision — реэкспорт из estimator.core."""

from estimator.core import SYSTEM_PROMPT as VISION_SYSTEM
from estimator.core import user_prompt_text as vision_user_text

__all__ = ["VISION_SYSTEM", "vision_user_text"]
