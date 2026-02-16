# NutriBot

Telegram-бот нутрициолог для трекинга питания, веса и целей по КБЖУ.

## Стек

- Python 3.11+
- aiogram 3.x
- OpenAI API (текст + vision)
- SQLAlchemy async + SQLite (или PostgreSQL через `DATABASE_URL`)

## Быстрый старт

1. Установить зависимости:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
2. Скопировать `.env.example` в `.env` и заполнить токены.
3. Запуск:
   - Обычный: `python3 -m bot.main`
   - С автоперезапуском при изменении кода: `python3 run_with_reload.py`

## Переменные окружения

- `TELEGRAM_BOT_TOKEN` — токен Telegram-бота
- `OPENAI_API_KEY` — ключ OpenAI API
- `DATABASE_URL` — опционально, URL PostgreSQL (`postgresql+asyncpg://...`)
- `SQLITE_PATH` — путь к SQLite-файлу, если `DATABASE_URL` не задан
- `OPENAI_MODEL_TEXT` — модель для текста (по умолчанию `gpt-4o-mini`)
- `OPENAI_MODEL_VISION` — модель для vision (по умолчанию `gpt-4o-mini`)
- `OPENAI_MAX_REQUESTS_PER_MINUTE` — лимит запросов к OpenAI на пользователя

## Команды

- `/start` — онбординг
- `/profile` — профиль и обновление целей
- `/today` — прогресс за сегодня
- `/stats` — статистика (`/stats day|week|month`)
- `/weight` — добавить текущий вес
- `/history` — приемы пищи за сегодня
- `/suggest` — рекомендации, чем добрать норму
- `/reset` — удалить данные
- `/help` — справка

## Деплой на Amvera

- В настройках приложения задайте `TELEGRAM_BOT_TOKEN` и `OPENAI_API_KEY`.
- Проект содержит `amvera.yaml` (Python Pip), команда запуска: `python3 -m bot.main`.
- Если используете SQLite, храните файл БД в постоянном хранилище Amvera: `SQLITE_PATH=/data/nutri.db`.
- Для продакшена предпочтительнее managed PostgreSQL (`DATABASE_URL`), чтобы не зависеть от файловой БД.

