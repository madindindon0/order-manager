"""Служебный скрипт: скриншоты вкладок GUI для README.

Использует ImageMagick ``import`` для захвата окон по идентификатору.
Не является частью приложения — запускается вручную::

    DISPLAY=:1 .venv/bin/python tools/capture_gui.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gui  # noqa: E402
from db import Storage  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "screenshots"


def capture(app: gui.OrderManagerApp, filename: str) -> None:
    """Сделать скриншот окна приложения.

    Parameters
    ----------
    app : OrderManagerApp
        Экземпляр приложения.
    filename : str
        Имя файла в каталоге ``screenshots/``.
    """
    app.update_idletasks()
    app.update()
    window_id = hex(app.winfo_id())
    dest = OUT_DIR / filename
    result = subprocess.run(
        ["import", "-display", ":1", "-window", window_id, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Не удалось снять {filename}: {result.stderr}", file=sys.stderr)
    else:
        print(f"OK: {dest}")


def main() -> None:
    """Снять скриншоты всех вкладок приложения."""
    storage = Storage(Path(__file__).resolve().parent.parent / "data" / "store.xlsx")
    if not storage.orders:
        storage.seed_demo_data()
    app = gui.OrderManagerApp(storage)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Вкладка «Клиенты»
    capture(app, "gui_clients.png")

    # Вкладка «Товары»
    app.nb.select(1)
    capture(app, "gui_products.png")

    # Вкладка «Заказы» — выберем первый заказ и покажем его статус
    app.nb.select(2)
    children = app.or_tree.get_children()
    if children:
        app.or_tree.selection_set(children[0])
        app._on_select_order()
    capture(app, "gui_orders.png")

    # Вкладка «Аналитика» — покажем график динамики заказов
    app.nb.select(3)
    app._report_dynamics()
    capture(app, "gui_analytics.png")

    app.destroy()
    print("Готово.")


if __name__ == "__main__":
    main()