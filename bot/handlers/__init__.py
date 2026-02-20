from bot.handlers.group import router as group_router
from bot.handlers.goal import router as goal_router
from bot.handlers.help import router as help_router
from bot.handlers.meal import router as meal_router
from bot.handlers.settings import router as settings_router
from bot.handlers.start import router as start_router
from bot.handlers.stats import router as stats_router
from bot.handlers.suggest import router as suggest_router
from bot.handlers.today import router as today_router
from bot.handlers.water import router as water_router
from bot.handlers.weight import router as weight_router

ALL_ROUTERS = [
    group_router,
    goal_router,
    start_router,
    settings_router,
    today_router,
    stats_router,
    weight_router,
    water_router,
    suggest_router,
    help_router,
    meal_router,
]

