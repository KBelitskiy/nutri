#!/usr/bin/env python3
"""
Запуск бота с автоперезапуском при изменении файлов.
Перед стартом и при каждом перезапуске запускаются автотесты; результат в одну строку.
Использование: python run_with_reload.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from collections.abc import Callable

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    print("Нужен пакет watchdog. Установите зависимости:")
    print("  pip3 install -r requirements.txt")
    sys.exit(1)


def run_tests(project_root: str) -> bool:
    """Запускает pytest и выводит итог в одну строку (X/Y passed). Возвращает True, если все тесты прошли."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=60,
    )
    out = (result.stdout + result.stderr).strip()
    passed = failed = total = 0
    for line in reversed(out.splitlines()):
        line = line.strip()
        # "48 passed in 1.07s" или "2 failed, 46 passed in 1.50s"
        m = re.search(r"(?:(\d+)\s+failed[,\s]+)?(\d+)\s+passed", line)
        if m:
            failed = int(m.group(1) or 0)
            passed = int(m.group(2))
            total = passed + failed
            break
    if total:
        part = f"{passed}/{total} passed"
        if failed:
            part += f", {failed} failed"
        # время из строки с итогом (например "in 1.07s")
        time_m = re.search(r"in\s+([\d.]+s)", line)
        if time_m:
            part += f" in {time_m.group(1)}"
        summary = part
    else:
        summary = "ok" if result.returncode == 0 else "FAILED"
    print(f"Tests: {summary}", flush=True)
    return result.returncode == 0


class RestartHandler(FileSystemEventHandler):
    def __init__(
        self, callback: Callable[[], None], *, grace_seconds: float = 2.0
    ) -> None:
        super().__init__()
        self._callback = callback
        self._debounce = 0.3
        self._last_call = 0.0
        self._grace_until = 0.0

    def set_grace_until(self, until: float) -> None:
        self._grace_until = until

    def _maybe_trigger(self, path: str, is_directory: bool) -> None:
        if is_directory:
            return
        if path.endswith(".py") and "__pycache__" not in path:
            now = time.monotonic()
            if now < self._grace_until:
                return
            if now - self._last_call >= self._debounce:
                self._last_call = now
                self._callback()

    def on_modified(self, event: FileSystemEvent) -> None:
        self._maybe_trigger(event.src_path, event.is_directory)

    def on_created(self, event: FileSystemEvent) -> None:
        self._maybe_trigger(event.src_path, event.is_directory)

    def on_moved(self, event: FileSystemEvent) -> None:
        # Многие редакторы сохраняют файл как "tmp -> rename", поэтому
        # отслеживаем также dest_path, чтобы не пропускать изменения.
        dest_path = getattr(event, "dest_path", "")
        self._maybe_trigger(dest_path or event.src_path, event.is_directory)


def main() -> None:
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    process: subprocess.Popen | None = None

    def start_bot() -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-m", "bot.main"],
            stdin=subprocess.DEVNULL,
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=project_root,
        )

    def restart() -> None:
        nonlocal process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        run_tests(project_root)
        process = start_bot()
        handler.set_grace_until(time.monotonic() + 2.0)
        print("\n--- перезапуск бота ---\n", flush=True)

    run_tests(project_root)
    process = start_bot()
    handler = RestartHandler(restart, grace_seconds=2.0)
    handler.set_grace_until(time.monotonic() + 2.0)
    observer = Observer()
    observer.schedule(handler, path=project_root, recursive=True)
    observer.start()

    try:
        while True:
            if process.poll() is not None:
                code = process.returncode
                print(f"\n--- процесс бота завершился (code={code}), перезапуск ---\n", flush=True)
                restart()
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
    observer.join(timeout=2)


if __name__ == "__main__":
    main()
