"""Автономный модуль оценки КБЖУ по фото еды.

Использование как библиотека:
    from estimator import analyze_meal_photo

Использование из CLI:
    python -m estimator photo.jpg
    python -m estimator photo.jpg --caption "200г курицы с рисом"
"""

from estimator.core import analyze_meal_photo

__all__ = ["analyze_meal_photo"]
