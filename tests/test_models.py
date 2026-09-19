"""Unit-тесты модуля :mod:`models`.

Покрывают классы данных, валидацию, инкапсуляцию, наследование,
полиморфизм, рекурсивные методы ``Category`` и сериализацию.

Запуск::

    python -m unittest tests.test_models -v
"""

import unittest
from datetime import date

from models import (
    Category,
    CorporateCustomer,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    RegularCustomer,
    ValidationError,
    VIPCustomer,
    order_status_allowed,
)


def make_customer(**kwargs):
    """Создать клиента с разумными значениями по умолчанию."""
    defaults = {
        "name": "Иван Петров",
        "email": "ivan@example.com",
        "phone": "+7 (900) 123-45-67",
        "city": "Москва",
    }
    defaults.update(kwargs)
    return Customer(**defaults)


class ProductTest(unittest.TestCase):
    """Тесты класса Product."""

    def test_valid_product(self):
        product = Product("Мышь", 1690.0, stock=10)
        self.assertEqual(product.name, "Мышь")
        self.assertEqual(product.price, 1690.0)
        self.assertEqual(product.stock, 10)

    def test_empty_name_raises(self):
        with self.assertRaises(ValidationError):
            Product("   ", 100.0)

    def test_negative_price_raises(self):
        with self.assertRaises(ValidationError):
            Product("Мышь", -5.0)

    def test_negative_stock_raises(self):
        with self.assertRaises(ValidationError):
            Product("Мышь", 5.0, stock=-1)

    def test_price_setter_protects_invariant(self):
        product = Product("Мышь", 100.0)
        with self.assertRaises(ValidationError):
            product.price = -10.0
        self.assertEqual(product.price, 100.0)

    def test_to_dict_from_dict_round_trip(self):
        product = Product("Клавиатура", 3990.0, stock=3)
        product.id = 7
        restored = Product.from_dict(product.to_dict())
        self.assertEqual(restored.id, 7)
        self.assertEqual(restored.name, "Клавиатура")
        self.assertEqual(restored.price, 3990.0)
        self.assertEqual(restored.stock, 3)


class CustomerValidationTest(unittest.TestCase):
    """Тесты валидации контактных данных клиента (регулярные выражения)."""

    def test_valid_email_accepted(self):
        self.assertEqual(make_customer(email="user.name+tag@sub.example.com").email, "user.name+tag@sub.example.com")

    def test_invalid_email_raises(self):
        for bad in ["not-an-email", "user@", "@example.com", "user@example", "user @x.ru"]:
            with self.subTest(email=bad):
                with self.assertRaises(ValidationError):
                    make_customer(email=bad)

    def test_valid_phone_accepted(self):
        for good in ["+7 (900) 123-45-67", "89001234567", "8 900 123 45 67", "+79001234567"]:
            with self.subTest(phone=good):
                make_customer(phone=good)

    def test_invalid_phone_raises(self):
        for bad in ["123", "abc", "+7 (900) 12-45-67", "+799912345678"]:
            with self.subTest(phone=bad):
                with self.assertRaises(ValidationError):
                    make_customer(phone=bad)

    def test_short_name_raises(self):
        with self.assertRaises(ValidationError):
            make_customer(name="И")

    def test_encapsulation_keeps_original_on_error(self):
        customer = make_customer()
        with self.assertRaises(ValidationError):
            customer.email = "плохой адрес"
        self.assertEqual(customer.email, "ivan@example.com")


class InheritancePolymorphismTest(unittest.TestCase):
    """Тесты наследования и полиморфизма скидок."""

    def test_discount_polymorphism(self):
        cases = [
            (Customer("Иван", "i@e.ru", "+79001234567"), 0.0),
            (RegularCustomer("Иван", "i@e.ru", "+79001234567"), 0.05),
            (VIPCustomer("Иван", "i@e.ru", "+79001234567"), 0.15),
            (CorporateCustomer("ООО Ромашка", "o@e.ru", "+79001234567", inn="7701234567"), 0.10),
        ]
        for customer, expected in cases:
            with self.subTest(customer=customer.customer_type()):
                self.assertAlmostEqual(customer.discount(), expected)

    def test_customer_type_names(self):
        self.assertEqual(
            [
                make_customer().customer_type(),
                VIPCustomer("Иваннов", "i@e.ru", "+79001234567").customer_type(),
            ],
            ["Customer", "VIPCustomer"],
        )

    def test_isinstance_hierarchy(self):
        vip = VIPCustomer("Иван", "i@e.ru", "+79001234567")
        self.assertIsInstance(vip, VIPCustomer)
        self.assertIsInstance(vip, Customer)
        self.assertTrue(issubclass(CorporateCustomer, Customer))

    def test_inherited_contact_info(self):
        customer = make_customer()
        self.assertEqual(customer.contact_info(), "ivan@example.com | +7 (900) 123-45-67")

    def test_vip_priority_validation(self):
        with self.assertRaises(ValidationError):
            VIPCustomer("Иван", "i@e.ru", "+79001234567", priority=0)

    def test_corporate_inn_validation(self):
        with self.assertRaises(ValidationError):
            CorporateCustomer("ООО", "o@e.ru", "+79001234567", inn="12345")
        corp = CorporateCustomer("ООО Ромашка", "o@e.ru", "+79001234567", inn="7701234567")
        with self.assertRaises(ValidationError):
            corp.inn = "ab"
        with self.assertRaises(ValidationError):
            corp.inn = "770123456789012"

    def test_registered_date_validation(self):
        with self.assertRaises(ValidationError):
            make_customer(registered="01.01.2025")


class OrderTest(unittest.TestCase):
    """Тесты заказа и позиций."""

    def setUp(self):
        self.customer = make_customer()
        self.mouse = Product("Мышь", 1690.0)
        self.keyboard = Product("Клавиатура", 3990.0)

    def test_order_total_sum(self):
        order = Order(self.customer, "2025-01-15")
        order.add_item(self.mouse, 2)
        order.add_item(self.keyboard, 1)
        self.assertAlmostEqual(order.total(), 2 * 1690.0 + 3990.0)
        self.assertEqual(order.item_count(), 3)

    def test_order_total_with_discount(self):
        vip = VIPCustomer("Иван", "i@e.ru", "+79001234567")
        order = Order(vip, "2025-01-15")
        order.add_item(self.mouse, 2)
        # 3380 * (1 - 0.15) = 2873.0
        self.assertAlmostEqual(order.total(), 2873.0)

    def test_valid_date_required(self):
        with self.assertRaises(ValidationError):
            Order(self.customer, "15/01/2025")

    def test_default_date_is_today(self):
        order = Order(self.customer)
        self.assertEqual(order.order_date, date.today().isoformat())

    def test_quantity_must_be_positive(self):
        order = Order(self.customer)
        with self.assertRaises(ValidationError):
            order.add_item(self.mouse, 0)
        with self.assertRaises(ValidationError):
            OrderItem(self.mouse, -3)

    def test_status_transition_guard(self):
        order = Order(self.customer)
        self.assertEqual(order.status, OrderStatus.NEW)
        order.status = OrderStatus.PAID
        self.assertEqual(order.status, OrderStatus.PAID)
        # Переход из "оплачен" сразу в "завершён" запрещён
        target = order_status_allowed(OrderStatus.PAID, OrderStatus.COMPLETED)
        order.status = target
        self.assertEqual(order.status, OrderStatus.PAID)

    def test_order_to_dict_from_dict(self):
        order = Order(self.customer, "2025-02-10")
        order.add_item(self.mouse, 2)
        order.id = 42
        data = order.to_dict()
        self.assertEqual(data["customer_name"], "Иван Петров")
        restored = Order.from_dict(data, self.customer)
        self.assertEqual(restored.id, 42)
        self.assertEqual(restored.order_date, "2025-02-10")
        self.assertEqual(restored.item_count(), 2)


class CustomerSerializationTest(unittest.TestCase):
    """Тесты полиморфной сериализации клиентов."""

    def _round_trip(self, customer):
        return Customer.from_dict(customer.to_dict())

    def test_regular_round_trip(self):
        restored = self._round_trip(RegularCustomer("Иван", "i@e.ru", "+79001234567"))
        self.assertEqual(restored.customer_type(), "RegularCustomer")
        self.assertAlmostEqual(restored.discount(), 0.05)

    def test_vip_round_trip_priority(self):
        vip = VIPCustomer("Иван", "i@e.ru", "+79001234567", priority=3)
        restored = self._round_trip(vip)
        self.assertEqual(restored.customer_type(), "VIPCustomer")
        self.assertEqual(restored.priority, 3)

    def test_corporate_round_trip_inn(self):
        corp = CorporateCustomer("ООО", "o@e.ru", "+79001234567", inn="7701234567")
        restored = self._round_trip(corp)
        self.assertEqual(restored.customer_type(), "CorporateCustomer")
        self.assertEqual(restored.inn, "7701234567")

    def test_orders_count_preserved(self):
        customer = make_customer()
        customer.orders_count = 5
        restored = self._round_trip(customer)
        self.assertEqual(restored.orders_count, 5)


class CategoryTreeTest(unittest.TestCase):
    """Тесты рекурсивных методов дерева категорий."""

    def setUp(self):
        self.electronics = Category("Электроника")
        self.computers = Category("Компьютеры", self.electronics)
        self.laptops = Category("Ноутбуки", self.computers)
        self.mice = Category("Мыши", self.computers)
        self.audio = Category("Аудио", self.electronics)

    def test_depth(self):
        self.assertEqual(self.electronics.depth(), 3)
        self.assertEqual(self.audio.depth(), 1)

    def test_count_nodes(self):
        self.assertEqual(self.electronics.count_nodes(), 5)

    def test_find_recursive(self):
        found = self.electronics.find("Мыши")
        self.assertIs(found, self.mice)
        self.assertIsNone(self.electronics.find("Отсутствует"))

    def test_iteration(self):
        names = {category.name for category in self.electronics}
        self.assertEqual(names, {"Электроника", "Компьютеры", "Ноутбуки", "Мыши", "Аудио"})

    def test_is_leaf(self):
        self.assertTrue(self.mice.is_leaf())
        self.assertFalse(self.electronics.is_leaf())


if __name__ == "__main__":
    unittest.main()