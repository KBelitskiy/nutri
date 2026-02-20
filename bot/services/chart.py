from __future__ import annotations

import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


_MODE_LABELS = {"light": "Лайт", "medium": "Медиум", "hard": "Хард"}
_MODE_COLORS = {"light": "#2E7D32", "medium": "#F9A825", "hard": "#C62828"}


def _parse_dates(items: list[dict]) -> tuple[list[datetime], list[float]]:
    dates = [datetime.fromisoformat(str(x["date"])) for x in items]
    weights = [float(x["weight_kg"]) for x in items]
    return dates, weights


def render_weight_plan_chart(
    forecast: list[dict],
    actual_weights: list[dict],
    target_weight: float,
    mode: str,
) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    plt.rcParams.update({"font.size": 12})

    if forecast:
        f_dates, f_weights = _parse_dates(forecast)
        ax.plot(
            f_dates,
            f_weights,
            linestyle="--",
            linewidth=2.5,
            color=_MODE_COLORS.get(mode, "#1565C0"),
            label=f"Прогноз ({_MODE_LABELS.get(mode, mode)})",
        )

    ax.axhline(
        y=target_weight,
        color="#455A64",
        linestyle=":",
        linewidth=2,
        label=f"Цель: {target_weight:.1f} кг",
    )

    if actual_weights:
        a_dates, a_weights = _parse_dates(actual_weights)
        ax.scatter(
            a_dates,
            a_weights,
            s=48,
            color="#283593",
            alpha=0.9,
            label="Фактические замеры",
            zorder=3,
        )

    ax.set_title(f"План изменения веса: режим {_MODE_LABELS.get(mode, mode)}", fontsize=14, pad=14)
    ax.set_xlabel("Дата", fontsize=12)
    ax.set_ylabel("Вес, кг", fontsize=12)
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=10)
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close(fig)
    return buffer


def render_three_scenarios_chart(
    forecasts: dict[str, list[dict]],
    current_weight: float,
    target_weight: float,
) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    plt.rcParams.update({"font.size": 12})

    for mode in ("light", "medium", "hard"):
        forecast = forecasts.get(mode) or []
        if not forecast:
            continue
        dates, weights = _parse_dates(forecast)
        ax.plot(
            dates,
            weights,
            linewidth=2.8,
            color=_MODE_COLORS[mode],
            label=f"{_MODE_LABELS[mode]}",
        )

    ax.axhline(
        y=target_weight,
        color="#455A64",
        linestyle=":",
        linewidth=2,
        label=f"Цель: {target_weight:.1f} кг",
    )
    ax.axhline(
        y=current_weight,
        color="#90A4AE",
        linestyle="--",
        linewidth=1.5,
        label=f"Текущий: {current_weight:.1f} кг",
    )

    ax.set_title("Сценарии достижения целевого веса", fontsize=14, pad=14)
    ax.set_xlabel("Дата", fontsize=12)
    ax.set_ylabel("Вес, кг", fontsize=12)
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=10)
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close(fig)
    return buffer
