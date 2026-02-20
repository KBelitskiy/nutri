"""January Food Benchmark (JFB) — оценка точности vision-модели бота.

Датасет: 1000 реальных фото блюд с валидированными аннотациями КБЖУ.
Источник: https://github.com/January-ai/food-scan-benchmarks
Лицензия: CC-BY-4.0

Использование:
    python -m benchmark.jfb                    # 50 изображений
    python -m benchmark.jfb --max-items 200    # 200 изображений
    python -m benchmark.jfb --max-items 0      # весь датасет (1000)
    python -m benchmark.jfb --model gpt-4o     # конкретная модель
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import csv
import json
import mimetypes
import os
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from estimator import analyze_meal_photo  # noqa: E402

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

DATASET_URL = (
    "https://january-food-image-dataset-public.s3.amazonaws.com/"
    "food-scan-benchmark-dataset.tar.gz"
)
CACHE_DIR = ROOT / ".benchmark_cache"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _download_progress(block_num: int, block_size: int, total_size: int) -> None:
    if total_size > 0:
        done = min(block_num * block_size, total_size)
        pct = done * 100 // total_size
        mb_done = done / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        print(f"\r  {mb_done:.0f}/{mb_total:.0f} MB ({pct}%)", end="", flush=True)


def _download_dataset() -> Path:
    """Скачать и распаковать JFB датасет (кэшируется)."""
    dataset_dir = CACHE_DIR / "food-scan-benchmark-dataset"
    csv_path = dataset_dir / "food_scan_bench_v1.csv"

    if csv_path.exists():
        return dataset_dir

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive = CACHE_DIR / "jfb.tar.gz"

    if not archive.exists():
        print("Скачиваю JFB датасет из S3…")
        try:
            import ssl

            ctx = ssl.create_default_context()
            try:
                urllib.request.urlretrieve(
                    DATASET_URL, archive, _download_progress, context=ctx
                )
            except TypeError:
                urllib.request.urlretrieve(DATASET_URL, archive, _download_progress)
            print()
        except Exception as exc:
            archive.unlink(missing_ok=True)
            print(
                f"\nОшибка загрузки: {exc}\n"
                "Скачайте вручную:\n"
                f"  curl -L -o {archive} '{DATASET_URL}'"
            )
            sys.exit(1)

    print("Распаковка…")
    with tarfile.open(archive) as tar:
        tar.extractall(path=CACHE_DIR)
    archive.unlink(missing_ok=True)
    print("Готово.\n")
    return dataset_dir


def _load_dataset(dataset_dir: Path, max_items: int) -> list[dict]:
    """Загрузить CSV с аннотациями и вернуть список сэмплов."""
    csv_path = dataset_dir / "food_scan_bench_v1.csv"
    img_dir = dataset_dir / "fsb_images"

    samples: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            img_path = img_dir / row["image_filename"]
            if not img_path.exists():
                continue
            samples.append(
                {
                    "image_id": row["image_id"],
                    "image_path": img_path,
                    "meal_name": row["meal_name"],
                    "gt": {
                        "calories": float(row["total_calories"]),
                        "protein": float(row["total_protein"]),
                        "fat": float(row["total_fat"]),
                        "carbs": float(row["total_carbs"]),
                    },
                }
            )

    if max_items > 0:
        samples = samples[:max_items]
    return samples


# ---------------------------------------------------------------------------
# Image → data URI
# ---------------------------------------------------------------------------


def _image_to_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


# ---------------------------------------------------------------------------
# Метрики
# ---------------------------------------------------------------------------

MACRO_KEYS = ("calories", "protein", "fat", "carbs")


def _wmape(gt: dict, pred: dict) -> float:
    """Weighted Mean Absolute Percentage Error по четырём макронутриентам."""
    abs_errors = sum(abs(gt[k] - pred.get(k, 0)) for k in MACRO_KEYS)
    sum_actuals = sum(abs(gt[k]) for k in MACRO_KEYS)
    if sum_actuals == 0:
        return 0.0 if abs_errors == 0 else 100.0
    return (abs_errors / sum_actuals) * 100


def _per_macro_ape(gt: dict, pred: dict) -> dict[str, float]:
    """Absolute Percentage Error по каждому макронутриенту."""
    result: dict[str, float] = {}
    for k in MACRO_KEYS:
        gt_val, pred_val = gt[k], pred.get(k, 0)
        if gt_val > 0:
            result[k] = abs(gt_val - pred_val) / gt_val * 100
        else:
            result[k] = 0.0 if pred_val == 0 else 100.0
    return result


def _per_macro_ae(gt: dict, pred: dict) -> dict[str, float]:
    """Absolute Error по каждому макронутриенту."""
    return {k: abs(gt[k] - pred.get(k, 0)) for k in MACRO_KEYS}


# ---------------------------------------------------------------------------
# Бенчмарк
# ---------------------------------------------------------------------------


async def run_benchmark(
    max_items: int,
    model: str,
    concurrency: int,
    results_file: str | None,
    csv_file: str | None,
) -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = (
        os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("BASE_URL", "").strip()
        or os.getenv("base_url", "").strip()
        or None
    )
    if not api_key:
        print("Ошибка: OPENAI_API_KEY не задан в .env")
        sys.exit(1)

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    print("=" * 64)
    print("  January Food Benchmark (JFB)")
    print(f"  Модель: {model}")
    print("=" * 64)

    dataset_dir = _download_dataset()
    samples = _load_dataset(dataset_dir, max_items)
    total = len(samples)
    print(f"Загружено {total} изображений\n")

    if total == 0:
        print("Нет изображений для оценки.")
        return

    results: list[dict] = []
    errors = 0
    semaphore = asyncio.Semaphore(concurrency)
    t0 = time.monotonic()

    async def process(idx: int, sample: dict) -> dict | None:
        nonlocal errors
        async with semaphore:
            data_uri = _image_to_data_uri(sample["image_path"])
            try:
                pred = await analyze_meal_photo(client, model, data_uri)
            except Exception as exc:
                errors += 1
                print(f"  [{idx + 1}/{total}] ОШИБКА: {exc}")
                return None

            pred_macros = {
                "calories": pred.get("calories", 0),
                "protein": pred.get("protein_g", 0),
                "fat": pred.get("fat_g", 0),
                "carbs": pred.get("carbs_g", 0),
            }
            gt = sample["gt"]
            wmape = _wmape(gt, pred_macros)
            ae = _per_macro_ae(gt, pred_macros)
            ape = _per_macro_ape(gt, pred_macros)

            name = sample["meal_name"][:40]
            print(
                f"  [{idx + 1}/{total}] {name:<40}  "
                f"wMAPE={wmape:5.1f}%  Δkcal={ae['calories']:+.0f}"
            )

            return {
                "image_id": sample["image_id"],
                "image_filename": sample["image_path"].name,
                "meal_name": sample["meal_name"],
                "gt": gt,
                "pred_macros": pred_macros,
                "pred_description": pred.get("description", ""),
                "wmape": wmape,
                "ape": ape,
                "ae": ae,
            }

    tasks = [process(i, s) for i, s in enumerate(samples)]
    completed = await asyncio.gather(*tasks)
    results = [r for r in completed if r is not None]
    elapsed = time.monotonic() - t0

    # ----- Итоги -----
    n = len(results)
    if n == 0:
        print("\nНет результатов для подсчёта.")
        return

    avg_wmape = sum(r["wmape"] for r in results) / n

    macro_labels = {
        "calories": ("Калории", "ккал"),
        "protein": ("Белки", "г"),
        "fat": ("Жиры", "г"),
        "carbs": ("Углеводы", "г"),
    }

    print()
    print("=" * 64)
    print("  РЕЗУЛЬТАТЫ")
    print("=" * 64)
    print(f"  Модель:            {model}")
    print(f"  Изображений:       {n} (ошибок: {errors})")
    print(f"  Общий wMAPE:       {avg_wmape:.1f}%")
    print(f"  Время:             {elapsed:.1f} с ({elapsed / n:.1f} с/фото)")
    print("-" * 64)
    print(f"  {'Макронутриент':<14} {'MAPE, %':>10} {'MAE':>10} {'Единица':>10}")
    print("-" * 64)
    for key, (label, unit) in macro_labels.items():
        mape = sum(r["ape"][key] for r in results) / n
        mae = sum(r["ae"][key] for r in results) / n
        print(f"  {label:<14} {mape:>9.1f}% {mae:>9.1f} {unit:>10}")
    print("=" * 64)

    sorted_results = sorted(results, key=lambda r: r["wmape"])
    print("\n  Лучшие 5 (наименьший wMAPE):")
    for r in sorted_results[:5]:
        print(f"    wMAPE={r['wmape']:5.1f}%  {r['meal_name'][:55]}")
    print("\n  Худшие 5 (наибольший wMAPE):")
    for r in sorted_results[-5:]:
        print(f"    wMAPE={r['wmape']:5.1f}%  {r['meal_name'][:55]}")

    print()
    print("-" * 64)
    print("  Референсные wMAPE (из статьи JFB, 1000 фото):")
    print("    january/food-vision-v1:  14.2%")
    print("    GPT-4o (Best-of-4):      23.5%")
    print("    GPT-4o (Average):        26.8%")
    print("    GPT-4o-mini (Best-of-4): 36.1%")
    print("    GPT-4o-mini (Average):   41.2%")
    print("=" * 64)

    if results_file:
        report = {
            "model": model,
            "images_evaluated": n,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 1),
            "wmape": round(avg_wmape, 2),
            "per_macro": {
                key: {
                    "mape": round(sum(r["ape"][key] for r in results) / n, 2),
                    "mae": round(sum(r["ae"][key] for r in results) / n, 2),
                }
                for key in MACRO_KEYS
            },
            "details": [
                {
                    "image_id": r["image_id"],
                    "meal_name": r["meal_name"],
                    "gt": r["gt"],
                    "pred": r["pred_macros"],
                    "wmape": round(r["wmape"], 2),
                }
                for r in results
            ],
        }
        out = Path(results_file)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\nJSON-отчёт сохранён в {out}")

    if csv_file:
        csv_fields = [
            "image_id",
            "image_filename",
            "meal_name",
            "pred_description",
            "gt_calories",
            "gt_protein",
            "gt_fat",
            "gt_carbs",
            "pred_calories",
            "pred_protein",
            "pred_fat",
            "pred_carbs",
            "wmape",
            "ape_calories",
            "ape_protein",
            "ape_fat",
            "ape_carbs",
            "ae_calories",
            "ae_protein",
            "ae_fat",
            "ae_carbs",
        ]
        out_csv = Path(csv_file)
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
            for r in sorted(results, key=lambda x: x["image_id"]):
                writer.writerow(
                    {
                        "image_id": r["image_id"],
                        "image_filename": r["image_filename"],
                        "meal_name": r["meal_name"],
                        "pred_description": r["pred_description"],
                        "gt_calories": r["gt"]["calories"],
                        "gt_protein": r["gt"]["protein"],
                        "gt_fat": r["gt"]["fat"],
                        "gt_carbs": r["gt"]["carbs"],
                        "pred_calories": r["pred_macros"]["calories"],
                        "pred_protein": r["pred_macros"]["protein"],
                        "pred_fat": r["pred_macros"]["fat"],
                        "pred_carbs": r["pred_macros"]["carbs"],
                        "wmape": round(r["wmape"], 2),
                        "ape_calories": round(r["ape"]["calories"], 2),
                        "ape_protein": round(r["ape"]["protein"], 2),
                        "ape_fat": round(r["ape"]["fat"], 2),
                        "ape_carbs": round(r["ape"]["carbs"], 2),
                        "ae_calories": round(r["ae"]["calories"], 1),
                        "ae_protein": round(r["ae"]["protein"], 1),
                        "ae_fat": round(r["ae"]["fat"], 1),
                        "ae_carbs": round(r["ae"]["carbs"], 1),
                    }
                )
        print(f"CSV-результаты сохранены в {out_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Запуск January Food Benchmark для оценки vision-модели",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=50,
        help="Количество изображений (0 = все 1000, по умолчанию 50)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Модель (по умолчанию из OPENAI_MODEL_VISION в .env)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Параллельных запросов к API (по умолчанию 5)",
    )
    parser.add_argument(
        "--results-file",
        type=str,
        default=None,
        help="Путь для сохранения сводки в JSON",
    )
    parser.add_argument(
        "--csv-file",
        type=str,
        default=None,
        help="Путь для сохранения результатов по каждому фото в CSV",
    )
    args = parser.parse_args()

    if args.model is None:
        load_dotenv()
        args.model = os.getenv("OPENAI_MODEL_VISION", "gpt-4o-mini")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.results_file is None:
        args.results_file = str(RESULTS_DIR / f"jfb_{args.model}_{args.max_items}.json")
    if args.csv_file is None:
        args.csv_file = str(RESULTS_DIR / f"jfb_{args.model}_{args.max_items}.csv")

    asyncio.run(
        run_benchmark(
            args.max_items,
            args.model,
            args.concurrency,
            args.results_file,
            args.csv_file,
        )
    )


if __name__ == "__main__":
    main()
