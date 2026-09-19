"""Анализ и визуализация данных системы учёта заказов.

Модуль использует ``pandas``, ``matplotlib``, ``seaborn`` и
``networkx`` для решения аналитических задач ТЗ:

- топ-5 клиентов по числу заказов (столбчатая диаграмма);
- динамика количества заказов по датам (линейная диаграмма);
- граф связей клиентов по географии и общим товарам.

Вычислительные функции (``top_customers``, ``orders_dynamics``,
``build_customer_graph``) возвращают чистые структуры данных
(``DataFrame``, ``NetworkX Graph``) и не зависят от отрисовки,
поэтому легко покрываются unit-тестами. Функции ``plot_*``
сохраняют графики в PNG-файлы.

Дополнительно модуль реализует собственную сортировку заказов
(:func:`sort_orders`) на базе рекурсивной сортировки слиянием.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# Бэкенд без графического окна: графики сохраняются в файлы.
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import seaborn as sns

from models import Customer, Order, OrderItem, Product

#: Папка по умолчанию для сохранения отчётов.
DEFAULT_REPORTS_DIR = Path("reports")

# Стиль графиков.
sns.set_theme(style="whitegrid", palette="deep")
# Гарантированный шрифт с кириллицей и символом рубля.
matplotlib.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Liberation Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------------------
# Вспомогательные функции (плоские DataFrame)
# ---------------------------------------------------------------------------
def orders_dataframe(orders: Sequence[Order]) -> pd.DataFrame:
    """Построить плоский DataFrame по списку заказов.

    Parameters
    ----------
    orders : Sequence[Order]
        Список заказов.

    Returns
    -------
    pd.DataFrame
        Таблица с колонками ``order_id``, ``customer_id``,
        ``customer_name``, ``customer_type``, ``order_date`` (datetime),
        ``status``, ``total``, ``item_count``.
    """
    rows = []
    for order in orders:
        rows.append(
            {
                "order_id": order.id,
                "customer_id": order.customer.id if order.customer else None,
                "customer_name": order.customer.name if order.customer else "",
                "customer_type": order.customer.customer_type() if order.customer else "",
                "order_date": pd.to_datetime(order.order_date),
                "status": order.status.value,
                "total": order.total(),
                "item_count": order.item_count(),
            }
        )
    return pd.DataFrame(rows)


def items_dataframe(orders: Sequence[Order]) -> pd.DataFrame:
    """Построить плоский DataFrame по позициям заказов.

    Parameters
    ----------
    orders : Sequence[Order]
        Список заказов.

    Returns
    -------
    pd.DataFrame
        Таблица с колонками ``order_id``, ``product_id``,
        ``product_name``, ``price``, ``quantity``, ``subtotal``.
    """
    rows = []
    for order in orders:
        for item in order.items:
            rows.append(
                {
                    "order_id": order.id,
                    "customer_id": order.customer.id if order.customer else None,
                    "product_id": item.product.id,
                    "product_name": item.product.name,
                    "price": item.product.price,
                    "quantity": item.quantity,
                    "subtotal": item.subtotal(),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Аналитические расчёты (чистые функции)
# ---------------------------------------------------------------------------
def top_customers(orders: Sequence[Order], top_n: int = 5) -> pd.DataFrame:
    """Топ-`top_n` клиентов по числу заказов.

    Parameters
    ----------
    orders : Sequence[Order]
        Список заказов.
    top_n : int, optional
        Количество позиций в рейтинге (по умолчанию 5).

    Returns
    -------
    pd.DataFrame
        Таблица с колонками ``customer_name``, ``orders_count``,
        ``total_spent``, отсортированная по числу заказов по убыванию.
    """
    df = orders_dataframe(orders)
    if df.empty:
        return pd.DataFrame(
            columns=["customer_name", "orders_count", "total_spent"]
        )
    grouped = (
        df.groupby("customer_name")
        .agg(orders_count=("order_id", "count"), total_spent=("total", "sum"))
        .reset_index()
        .sort_values(["orders_count", "total_spent"], ascending=False)
    )
    return grouped.head(top_n).reset_index(drop=True)


def orders_dynamics(orders: Sequence[Order], freq: str = "W") -> pd.DataFrame:
    """Динамика количества заказов во времени.

    Parameters
    ----------
    orders : Sequence[Order]
        Список заказов.
    freq : str, optional
        Период агрегации pandas: ``D`` (день), ``W`` (неделя),
        ``ME`` (месяц). По умолчанию ``W``.

    Returns
    -------
    pd.DataFrame
        Таблица с колонками ``period`` (DatetimeIndex) и ``orders_count``.
    """
    df = orders_dataframe(orders)
    if df.empty:
        return pd.DataFrame(columns=["period", "orders_count"])
    series = (
        df.set_index("order_date")["order_id"]
        .resample(freq)
        .count()
        .rename("orders_count")
        .fillna(0)
        .astype(int)
    )
    result = series.reset_index()
    result.columns = ["period", "orders_count"]
    return result


def sales_by_category(orders: Sequence[Order]) -> pd.DataFrame:
    """Продажи по категориям товаров.

    Parameters
    ----------
    orders : Sequence[Order]
        Список заказов.

    Returns
    -------
    pd.DataFrame
        Таблица с колонками ``category`` и ``revenue``,
        отсортированная по выручке по убыванию.
    """
    items = items_dataframe(orders)
    if items.empty:
        return pd.DataFrame(columns=["category", "revenue"])
    revenue = (items["price"] * items["quantity"]).groupby(items["product_name"])
    return (
        revenue.sum()
        .rename("revenue")
        .reset_index()
        .rename(columns={"product_name": "product"})
        .sort_values("revenue", ascending=False)
    )


def build_customer_graph(
    customers: Sequence[Customer],
    orders: Sequence[Order],
    tie_by: Tuple[str, ...] = ("product", "city"),
) -> nx.Graph:
    """Построить граф связей клиентов.

    Вершины графа — клиенты; рёбра соединяют клиентов с общими
    товарами в заказах (``product``) или проживающих в одном городе
    (``city``). Размер вершины пропорционален числу заказов.

    Parameters
    ----------
    customers : Sequence[Customer]
        Список клиентов.
    orders : Sequence[Order]
        Список заказов.
    tie_by : Tuple[str, ...], optional
        Какие связи учитывать: ``product`` и/или ``city``.

    Returns
    -------
    networkx.Graph
        Граф связей; атрибуты вершин: ``orders_count``, ``city``,
        атрибуты рёбер: ``weight``, ``kind``.
    """
    graph = nx.Graph()
    for customer in customers:
        if customer.id is None:
            continue
        graph.add_node(
            customer.id,
            name=customer.name,
            city=customer.city,
            orders_count=customer.orders_count,
        )

    def add_edge(a: int, b: int, kind: str) -> None:
        if a == b or a is None or b is None:
            return
        if graph.has_edge(a, b):
            graph[a][b]["weight"] += 1
        else:
            graph.add_edge(a, b, weight=1, kind=kind)

    if "product" in tie_by:
        bought: Dict[int, set] = {}
        for order in orders:
            if order.customer and order.customer.id is not None:
                product_ids = {it.product.id for it in order.items if it.product.id is not None}
                bought.setdefault(order.customer.id, set()).update(product_ids)
        purchase_by_product: Dict[int, List[int]] = {}
        for customer_id, products in bought.items():
            for product_id in products:
                purchase_by_product.setdefault(product_id, []).append(customer_id)
        for product_id, client_ids in purchase_by_product.items():
            for i, a in enumerate(client_ids):
                for b in client_ids[i + 1 :]:
                    add_edge(a, b, "product")

    if "city" in tie_by:
        by_city: Dict[str, List[int]] = {}
        for customer in customers:
            if customer.city and customer.id is not None:
                by_city.setdefault(customer.city, []).append(customer.id)
        for city, client_ids in by_city.items():
            for i, a in enumerate(client_ids):
                for b in client_ids[i + 1 :]:
                    add_edge(a, b, "city")

    return graph


# ---------------------------------------------------------------------------
# Сортировка заказов (рекурсивная сортировка слиянием)
# ---------------------------------------------------------------------------
def _merge(
    left: List[Order],
    right: List[Order],
    key: Callable[[Order], object],
    reverse: bool,
) -> List[Order]:
    """Слить два отсортированных списка.

    Parameters
    ----------
    left, right : List[Order]
        Отсортированные списки заказов.
    key : Callable[[Order], object]
        Функция ключа сравнения.
    reverse : bool
        Сортировка по убыванию.
    """
    merged: List[Order] = []
    i = j = 0
    while i < len(left) and j < len(right):
        a, b = key(left[i]), key(right[j])
        take_left = a > b if reverse else a <= b
        merged.append(left[i] if take_left else right[j])
        if take_left:
            i += 1
        else:
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def merge_sort_orders(
    orders: Sequence[Order],
    key: Callable[[Order], object],
    reverse: bool = False,
) -> List[Order]:
    """Собственная сортировка заказов (рекурсивное слияние).

    Parameters
    ----------
    orders : Sequence[Order]
        Список заказов.
    key : Callable[[Order], object]
        Функция, извлекающая значение для сравнения
        (например, ``lambda o: o.order_date``).
    reverse : bool, optional
        Сортировка по убыванию (по умолчанию ``False``).

    Returns
    -------
    List[Order]
        Новый отсортированный список заказов.

    Examples
    --------
    >>> import analysis
    >>> analysis.sort_orders(orders, key=lambda o: o.order_date, reverse=True)
    """
    items = list(orders)
    if len(items) <= 1:
        return items
    mid = len(items) // 2
    left = merge_sort_orders(items[:mid], key, reverse)
    right = merge_sort_orders(items[mid:], key, reverse)
    return _merge(left, right, key, reverse)


def sort_orders(
    orders: Sequence[Order],
    by: str = "date",
    reverse: bool = False,
) -> List[Order]:
    """Отсортировать заказы по дате или стоимости.

    Обёртка над :func:`merge_sort_orders` с готовыми ключами.
    Использует лямбда-выражения для извлечения ключей.

    Parameters
    ----------
    orders : Sequence[Order]
        Список заказов.
    by : str, optional
        Критерий сортировки: ``date`` или ``total`` (по умолчанию ``date``).
    reverse : bool, optional
        Сортировка по убыванию.

    Returns
    -------
    List[Order]
        Отсортированный список заказов.

    Raises
    ------
    ValueError
        При неизвестном критерии сортировки.
    """
    keys: Dict[str, Callable[[Order], object]] = {
        "date": lambda order: order.order_date,
        "total": lambda order: order.total(),
    }
    if by not in keys:
        raise ValueError(f"Неизвестный критерий сортировки: {by!r}")
    return merge_sort_orders(orders, keys[by], reverse=reverse)


# ---------------------------------------------------------------------------
# Визуализация
# ---------------------------------------------------------------------------
def _ensure_dir(path: Path) -> None:
    """Создать каталог для отчёта, если его нет."""
    path.parent.mkdir(parents=True, exist_ok=True)


def plot_top_customers(top_df: pd.DataFrame, dest: str | Path = "reports/top_customers.png") -> Path:
    """Построить диаграмму топ-клиентов по числу заказов.

    Parameters
    ----------
    top_df : pd.DataFrame
        Результат :func:`top_customers`.
    dest : str | Path, optional
        Путь сохранения PNG-файла.

    Returns
    -------
    Path
        Путь к сохранённому изображению.
    """
    dest = Path(dest)
    _ensure_dir(dest)
    fig, ax = plt.subplots(figsize=(9, 5))
    if not top_df.empty:
        sns.barplot(
            data=top_df,
            x="customer_name",
            y="orders_count",
            hue="customer_name",
            legend=False,
            ax=ax,
        )
        ax.set_ylabel("Количество заказов")
        ax.set_title("Топ клиентов по числу заказов")
        for container in ax.containers:
            ax.bar_label(container)
    else:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center", transform=ax.transAxes)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    fig.savefig(dest, dpi=150)
    plt.close(fig)
    return dest


def plot_orders_dynamics(
    dyn_df: pd.DataFrame,
    dest: str | Path = "reports/orders_dynamics.png",
) -> Path:
    """Построить график динамики заказов по периодам.

    Parameters
    ----------
    dyn_df : pd.DataFrame
        Результат :func:`orders_dynamics`.
    dest : str | Path, optional
        Путь сохранения PNG-файла.

    Returns
    -------
    Path
        Путь к сохранённому изображению.
    """
    dest = Path(dest)
    _ensure_dir(dest)
    fig, ax = plt.subplots(figsize=(10, 5))
    if not dyn_df.empty:
        sns.lineplot(data=dyn_df, x="period", y="orders_count", marker="o", ax=ax)
        ax.set_ylabel("Количество заказов")
        ax.set_xlabel("Период")
        ax.set_title("Динамика количества заказов")
        plt.xticks(rotation=30, ha="right")
    else:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center", transform=ax.transAxes)
    plt.tight_layout()
    fig.savefig(dest, dpi=150)
    plt.close(fig)
    return dest


def plot_sales_by_category(
    sales_df: pd.DataFrame,
    dest: str | Path = "reports/sales_by_category.png",
) -> Path:
    """Построить горизонтальную диаграмму продаж по товарам.

    Parameters
    ----------
    sales_df : pd.DataFrame
        Результат :func:`sales_by_category`.
    dest : str | Path, optional
        Путь сохранения PNG-файла.

    Returns
    -------
    Path
        Путь к сохранённому изображению.
    """
    dest = Path(dest)
    _ensure_dir(dest)
    fig, ax = plt.subplots(figsize=(9, 6))
    if not sales_df.empty:
        data = sales_df.head(10)
        sns.barplot(
            data=data,
            y="product",
            x="revenue",
            hue="product",
            legend=False,
            ax=ax,
        )
        ax.set_title("Топ товаров по выручке")
        ax.set_xlabel("Выручка, руб.")
    else:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center", transform=ax.transAxes)
    plt.tight_layout()
    fig.savefig(dest, dpi=150)
    plt.close(fig)
    return dest


def plot_customer_graph(
    graph: nx.Graph,
    dest: str | Path = "reports/customer_graph.png",
) -> Path:
    """Визуализировать граф связей клиентов.

    Parameters
    ----------
    graph : networkx.Graph
        Граф, полученный из :func:`build_customer_graph`.
    dest : str | Path, optional
        Путь сохранения PNG-файла.

    Returns
    -------
    Path
        Путь к сохранённому изображению.
    """
    dest = Path(dest)
    _ensure_dir(dest)
    fig, ax = plt.subplots(figsize=(11, 8))
    if graph.number_of_nodes() == 0:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center", transform=ax.transAxes)
    else:
        sizes = [10 + 30 * graph.nodes[node].get("orders_count", 1) for node in graph.nodes]
        pos = nx.spring_layout(graph, seed=42, k=0.6)
        nx.draw_networkx_nodes(graph, pos, node_size=sizes, node_color="#4C72B0", alpha=0.85, ax=ax)
        if graph.number_of_edges() > 0:
            weights = [graph[u][v]["weight"] for u, v in graph.edges]
            nx.draw_networkx_edges(
                graph, pos, alpha=0.3, width=[0.5 + w for w in weights], ax=ax
            )
        labels = {
            node: (graph.nodes[node].get("name", "") or "").split()[0]
            for node in graph.nodes
        }
        nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8, ax=ax)
        ax.set_title("Граф связей клиентов")
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(dest, dpi=150)
    plt.close(fig)
    return dest


def run_all_reports(
    customers: Sequence[Customer],
    orders: Sequence[Order],
    dest_dir: str | Path = DEFAULT_REPORTS_DIR,
) -> Dict[str, Path]:
    """Сформировать все отчёты и сохранить графики.

    Parameters
    ----------
    customers : Sequence[Customer]
        Список клиентов.
    orders : Sequence[Order]
        Список заказов.
    dest_dir : str | Path, optional
        Каталог сохранения графиков.

    Returns
    -------
    Dict[str, Path]
        Словарь ``{имя_отчёта: путь_к_файлу}``.
    """
    dest_dir = Path(dest_dir)
    top_df = top_customers(orders)
    dyn_df = orders_dynamics(orders, freq="W")
    sales_df = sales_by_category(orders)
    graph = build_customer_graph(customers, orders)

    return {
        "top_customers": plot_top_customers(top_df, dest_dir / "top_customers.png"),
        "orders_dynamics": plot_orders_dynamics(dyn_df, dest_dir / "orders_dynamics.png"),
        "sales_by_category": plot_sales_by_category(sales_df, dest_dir / "sales_by_category.png"),
        "customer_graph": plot_customer_graph(graph, dest_dir / "customer_graph.png"),
    }