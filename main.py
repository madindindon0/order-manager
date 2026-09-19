"""Точка входа в систему учёта заказов интернет-магазина.

Примеры запуска::

    python main.py            # запустить графический интерфейс
    python main.py --demo     # перезаписать хранилище демо-данными и запустить GUI
    python main.py --reports  # сформировать отчёты без запуска GUI
    python main.py --seed     # только заполнить хранилище демо-данными
    python main.py --path data/store.xlsx  # указать файл хранилища
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from db import Storage, StorageError

# Путь к хранилищу по умолчанию (относительно корня проекта).
DEFAULT_STORAGE = Path(__file__).resolve().parent / "data" / "store.xlsx"


def build_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов командной строки.

    Returns
    -------
    argparse.ArgumentParser
        Настроенный парсер аргументов.
    """
    parser = argparse.ArgumentParser(
        prog="order_manager",
        description="Система учёта заказов интернет-магазина (итоговая аттестация по Python).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_STORAGE,
        help="Путь к файлу хранилища .xlsx (по умолчанию data/store.xlsx)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Заполнить хранилище демонстрационными данными и запустить GUI",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Только заполнить хранилище демонстрационными данными (без GUI)",
    )
    parser.add_argument(
        "--reports",
        action="store_true",
        help="Сформировать все отчёты в папку reports/ (без GUI)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports"),
        help="Каталог для сохранения отчётов (по умолчанию reports/)",
    )
    return parser


def main(argv=None) -> int:
    """Главная функция приложения.

    Parameters
    ----------
    argv : Optional[List[str]], optional
        Аргументы командной строки (по умолчанию ``sys.argv[1:]``).

    Returns
    -------
    int
        Код возврата: 0 при успехе, 1 при ошибке.
    """
    args = build_parser().parse_args(argv)

    try:
        storage = Storage(args.path)
    except StorageError as exc:
        print(f"Ошибка хранилища: {exc}", file=sys.stderr)
        return 1

    if args.seed:
        try:
            storage.seed_demo_data()
            print(f"Демо-данные сохранены в {args.path}")
            return 0
        except StorageError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1

    if args.demo:
        try:
            storage.seed_demo_data()
        except StorageError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1

    if args.reports:
        try:
            import analysis

            paths = analysis.run_all_reports(
                storage.customers, storage.orders, dest_dir=args.reports_dir
            )
            for name, path in paths.items():
                print(f"{name}: {path}")
            return 0
        except Exception as exc:
            print(f"Не удалось сформировать отчёты: {exc}", file=sys.stderr)
            return 1

    try:
        import gui

        gui.run_app(storage)
    except ImportError as exc:
        print(f"GUI недоступен: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())