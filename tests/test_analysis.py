"""Unit-тесты модуля :mod:`analysis`.

Покрывают чистые вычислительные функции анализа данных:
топ клиентов, динамику заказов, продажи по товарам, граф связей
и собственную сортировку заказов (рекурсивное слияние).

Запуск::

    python -m unittest tests.test_analysis -v
"""

import unittest

import analysis
from db import sample_data
from models import Customer, Order, OrderStatus, Product, RegularCustomer


def build_orders() -> list:
    """Построить небольшой фиксированный набор заказов."""
    alice = RegularCustomer("Алиса Иванова", "alice@example.com", "+79001112233", city="Москва")
    bob = RegularCustomer("Борис Петров", "bob@example.com", "+79004445566", city="Москва")
    carol = RegularCustomer("Катя Сидорова", "carol@example.com", "+79007778899", city="Казань")
    dave = Customer("Дима Козлов", "dave@example.com", "+79000001122", city="Казань")
    for idx, customer in enumerate((alice, bob, carol, dave), start=1):
        customer.id = idx

    mouse = Product("Мышь", 1000.0)
    phone = Product("Телефон", 5000.0)
    laptop = Product("Ноутбук", 30000.0)
    for idx, product in enumerate((mouse, phone, laptop), start=1):
        product.id = idx

    orders = []
    orders.append(make_order(1, alice, "2025-01-05", [(mouse, 1)]))
    orders.append(make_order(2, alice, "2025-01-10", [(phone, 1)]))
    orders.append(make_order(3, alice, "2025-02-01", [(laptop, 1)]))
    orders.append(make_order(4, bob, "2025-02-03", [(mouse, 2), (phone, 1)]))
    orders.append(make_order(5, bob, "2025-02-20", [(laptop, 1)]))
    orders.append(make_order(6, carol, "2025-03-01", [(mouse, 1)]))
    orders.append(make_order(7, dave, "2025-03-15", [(phone, 1)]))
    return orders


def make_order(order_id, customer, order_date, item_specs):
    """Создать заказ с позициями вида ``[(product, qty), ...]``."""
    order = Order(customer, order_date)
    for product, quantity in item_specs:
        order.add_item(product, quantity)
    order.id = order_id
    customer.orders_count += 1
    return order


class TopCustomersTest(unittest.TestCase):
    """Тесты расчёта топ-клиентов по числу заказов."""

    def setUp(self):
        self.orders = build_orders()

    def test_top_customers_order_and_counts(self):
        df = analysis.top_customers(self.orders, top_n=5)
        self.assertEqual(
            list(df["customer_name"]),
            ["Алиса Иванова", "Борис Петров", "Дима Козлов", "Катя Сидорова"],
        )
        self.assertEqual(list(df["orders_count"]), [3, 2, 1, 1])
        # Цены с учётом скидки обычных клиентов 5 %:
        # Алиса: (1000 + 5000 + 30000) * 0.95 = 34200
        self.assertAlmostEqual(df.loc[0, "total_spent"], 34200.0)

    def test_top_n_limits(self):
        df = analysis.top_customers(self.orders, top_n=2)
        self.assertEqual(len(df), 2)

    def test_empty_orders(self):
        df = analysis.top_customers([])
        self.assertTrue(df.empty)

    def test_top_customers_from_demo_set(self):
        _, _, orders, _ = sample_data(seed=7)
        df = analysis.top_customers(orders)
        self.assertEqual(len(df), 5)
        # Количество заказов не возрастает по строкам рейтинга (по убыванию)
        self.assertTrue((df["orders_count"].diff().fillna(0) <= 0).all())


class OrdersDynamicsTest(unittest.TestCase):
    """Тесты динамики количества заказов."""

    def setUp(self):
        self.orders = build_orders()

    def test_monthly_dynamics(self):
        df = analysis.orders_dynamics(self.orders, freq="ME")
        self.assertEqual(len(df), 3)  # январь, февраль, март
        self.assertEqual(int(df["orders_count"].sum()), len(self.orders))

    def test_daily_dynamics(self):
        df = analysis.orders_dynamics(self.orders, freq="D")
        self.assertEqual(int(df["orders_count"].sum()), 7)

    def test_empty_orders(self):
        df = analysis.orders_dynamics([], freq="W")
        self.assertTrue(df.empty)


class SalesByCategoryTest(unittest.TestCase):
    """Тесты расчёта продаж по товарам."""

    def setUp(self):
        self.orders = build_orders()

    def test_sales_sorted_desc(self):
        df = analysis.sales_by_category(self.orders)
        self.assertEqual(df.iloc[0]["product"], "Ноутбук")  # 30000*1 + 30000*1
        self.assertAlmostEqual(df["revenue"].sum(), 1000 * 4 + 5000 * 3 + 30000 * 2)

    def test_empty_orders(self):
        self.assertTrue(analysis.sales_by_category([]).empty)


class CustomerGraphTest(unittest.TestCase):
    """Тесты построения графа связей клиентов."""

    def setUp(self):
        self.orders = build_orders()
        unique = {}
        for order in self.orders:
            unique[order.customer.id] = order.customer
        self.customers = list(unique.values())

    def test_graph_has_all_customers(self):
        graph = analysis.build_customer_graph(self.customers, self.orders)
        self.assertEqual(graph.number_of_nodes(), len(self.customers))

    def test_edge_by_shared_product(self):
        graph = analysis.build_customer_graph(self.customers, self.orders, tie_by=("product",))
        # Алиса и Борис оба купили ноутбук и телефон -> минимум одно ребро
        edges = {(u, v) for u, v in graph.edges if graph.nodes[u]["name"] == "Алиса Иванова"}
        self.assertTrue(edges)

    def test_edge_by_city(self):
        graph = analysis.build_customer_graph(self.customers, self.orders, tie_by=("city",))
        cities = {graph.nodes[n]["city"] for n in graph.nodes}
        edge_cities = []
        for u, v in graph.edges:
            cu, cv = graph.nodes[u]["city"], graph.nodes[v]["city"]
            if cu == cv:
                edge_cities.append(cu)
        self.assertTrue(edge_cities)  # существуют рёбра внутри одного города

    def test_empty_data(self):
        graph = analysis.build_customer_graph([], [], tie_by=("product", "city"))
        self.assertEqual(graph.number_of_nodes(), 0)
        self.assertEqual(graph.number_of_edges(), 0)


class SortOrdersTest(unittest.TestCase):
    """Тесты собственной сортировки заказов."""

    def setUp(self):
        self.orders = build_orders()

    def test_sort_by_date_ascending(self):
        sorted_orders = analysis.sort_orders(self.orders, by="date")
        dates = [order.order_date for order in sorted_orders]
        self.assertEqual(dates, sorted(dates))

    def test_sort_by_date_descending(self):
        sorted_orders = analysis.sort_orders(self.orders, by="date", reverse=True)
        dates = [order.order_date for order in sorted_orders]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_sort_by_total(self):
        sorted_orders = analysis.sort_orders(self.orders, by="total")
        totals = [order.total() for order in sorted_orders]
        self.assertEqual(totals, sorted(totals))

    def test_invalid_criterion(self):
        with self.assertRaises(ValueError):
            analysis.sort_orders(self.orders, by="unknown")

    def test_single_element_list(self):
        self.assertEqual(len(analysis.sort_orders([self.orders[0]])), 1)

    def test_empty_list(self):
        self.assertEqual(analysis.sort_orders([]), [])

    def test_stability_with_equal_keys(self):
        orders = [self.orders[0], self.orders[1], self.orders[0]]
        result = analysis.sort_orders(orders, by="total")
        # Равные ключи сохраняют относительный порядок (устойчивость)
        self.assertEqual([order.id for order in result], [1, 1, 2])


if __name__ == "__main__":
    unittest.main()