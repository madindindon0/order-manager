"""Модели данных системы учёта заказов интернет-магазина.

Модуль реализует предметную область проекта:
товары, клиентов и заказы. Классы построены на принципах ООП:

- :ref:`encapsulation` — приватные атрибуты (``_name``, ``_email`` и т.д.)
  доступны только через свойства (``@property``) с проверкой значений;
- :ref:`inheritance` — иерархия ``Person -> Customer ->
  RegularCustomer/VIPCustomer/CorporateCustomer``;
- :ref:`polymorphism` — переопределение ``to_dict``/``from_dict``,
  ``__str__`` и ``discount`` в подклассах.

Дополнительно модуль содержит класс ``Category`` — дерево категорий
товаров с рекурсивными методами (``depth``, ``find``), демонстрирующими
использование рекурсии.

Пример использования::

    >>> from models import Product, RegularCustomer, Order
    >>> customer = RegularCustomer("Иван", "ivan@example.com", "+7 (900) 123-45-67")
    >>> order = Order(customer)
    >>> order.add_item(Product("Мышь", 1500), 2)
    >>> order.total()
    3000.0
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional, Tuple

import validators


class ValidationError(ValueError):
    """Ошибка валидации данных модели.

    Возникает при нарушении инвариантов объекта
    (некорректный email, отрицательная цена и т.п.).
    """


class Category:
    """Дерево категорий товаров.

    Демонстрирует рекурсивные алгоритмы обхода дерева.

    Parameters
    ----------
    name : str
        Название категории.
    parent : Optional[Category], optional
        Родительская категория. Если указана, категория
        автоматически добавляется в её список потомков.
    """

    def __init__(self, name: str, parent: Optional["Category"] = None) -> None:
        self._name = str(name)
        self._children: List["Category"] = []
        if parent is not None:
            parent.add_child(self)

    @property
    def name(self) -> str:
        """Название категории."""
        return self._name

    @property
    def children(self) -> Tuple["Category", ...]:
        """Неизменяемый кортеж дочерних категорий."""
        return tuple(self._children)

    def add_child(self, category: "Category") -> None:
        """Добавить дочернюю категорию.

        Parameters
        ----------
        category : Category
            Добавляемая категория.
        """
        if not isinstance(category, Category):
            raise TypeError("Дочерний элемент должен быть Category")
        if category is not self and category not in self._children:
            self._children.append(category)

    def is_leaf(self) -> bool:
        """Является ли категория листом (не имеет потомков)."""
        return not self._children

    def depth(self) -> int:
        """Рекурсивно вычислить глубину поддерева.

        Returns
        -------
        int
            Глубина дерева: 1 для листа, иначе 1 + максимум
            глубин дочерних поддеревьев.
        """
        if not self._children:
            return 1
        return 1 + max(child.depth() for child in self._children)

    def count_nodes(self) -> int:
        """Рекурсивно подсчитать количество узлов в поддереве.

        Returns
        -------
        int
            Количество категорий, включая саму категорию.
        """
        return 1 + sum(child.count_nodes() for child in self._children)

    def find(self, name: str) -> Optional["Category"]:
        """Рекурсивно найти категорию по названию.

        Parameters
        ----------
        name : str
            Искомое название категории.

        Returns
        -------
        Optional[Category]
            Найденная категория или ``None``.
        """
        if self._name == name:
            return self
        for child in self._children:
            found = child.find(name)
            if found is not None:
                return found
        return None

    def __iter__(self):
        """Обход поддерева в глубину (рекурсивный генератор)."""
        yield self
        for child in self._children:
            yield from child

    def __str__(self) -> str:
        return self._name


class Product:
    """Товар интернет-магазина.

    Инкапсулирует название, цену, категорию и остаток на складе.
    Цена и остаток защищены свойствами с проверкой неотрицательности.

    Parameters
    ----------
    name : str
        Название товара.
    price : float
        Цена за единицу, не может быть отрицательной.
    category : Optional[Category], optional
        Категория товара.
    stock : int, optional
        Остаток на складе (>= 0).
    """

    def __init__(
        self,
        name: str,
        price: float,
        category: Optional[Category] = None,
        stock: int = 0,
    ) -> None:
        self._id: Optional[int] = None
        self._name = ""
        self._price = 0.0
        self._category: Optional[Category] = None
        self._stock = 0
        self.name = name
        self.price = price
        self.category = category
        self.stock = stock

    @property
    def id(self) -> Optional[int]:
        """Уникальный идентификатор товара (назначается хранилищем)."""
        return self._id

    @id.setter
    def id(self, value: Optional[int]) -> None:
        self._id = int(value) if value is not None else None

    @property
    def name(self) -> str:
        """Название товара."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        value = str(value).strip()
        if not value:
            raise ValidationError("Название товара не может быть пустым")
        self._name = value

    @property
    def price(self) -> float:
        """Цена за единицу товара."""
        return self._price

    @price.setter
    def price(self, value: float) -> None:
        value = float(value)
        if value < 0:
            raise ValidationError("Цена товара не может быть отрицательной")
        self._price = value

    @property
    def category(self) -> Optional[Category]:
        """Категория товара."""
        return self._category

    @category.setter
    def category(self, value: Optional[Category]) -> None:
        if value is not None and not isinstance(value, Category):
            raise TypeError("Категория должна быть экземпляром Category")
        self._category = value

    @property
    def stock(self) -> int:
        """Остаток товара на складе."""
        return self._stock

    @stock.setter
    def stock(self, value: int) -> None:
        value = int(value)
        if value < 0:
            raise ValidationError("Остаток на складе не может быть отрицательным")
        self._stock = value

    def to_dict(self) -> dict:
        """Представить товар как словарь (для сериализации)."""
        return {
            "id": self._id,
            "name": self._name,
            "price": self._price,
            "category": self._category.name if self._category else None,
            "stock": self._stock,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        """Создать товар из словаря (полиморфная фабрика).

        Parameters
        ----------
        data : dict
            Словарь с ключами ``id``, ``name``, ``price``,
            ``category``, ``stock``.

        Returns
        -------
        Product
            Новый экземпляр товара.
        """
        product = cls(
            name=data["name"],
            price=data["price"],
            stock=data.get("stock", 0),
        )
        product._id = data.get("id")
        return product

    def __str__(self) -> str:
        return f"{self._name} ({self._price:.2f} ₽)"

    def __repr__(self) -> str:
        return f"Product(name={self._name!r}, price={self._price:.2f})"


class Person:
    """Базовый класс физического лица.

    Содержит общие контактные данные: имя, email, телефон, город.
    Email и телефон проверяются регулярными выражениями из модуля
    :mod:`validators` (инкапсуляция через свойства).

    Parameters
    ----------
    name : str
        Полное имя.
    email : str
        Адрес электронной почты.
    phone : str
        Номер телефона.
    city : str, optional
        Город проживания.
    """

    def __init__(self, name: str, email: str, phone: str, city: str = "") -> None:
        self._id: Optional[int] = None
        self._name = ""
        self._email = ""
        self._phone = ""
        self._city = ""
        self.name = name
        self.email = email
        self.phone = phone
        self.city = city

    @property
    def id(self) -> Optional[int]:
        """Уникальный идентификатор (назначается хранилищем)."""
        return self._id

    @id.setter
    def id(self, value: Optional[int]) -> None:
        self._id = int(value) if value is not None else None

    @property
    def name(self) -> str:
        """Имя клиента или сотрудника."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        value = str(value).strip()
        if len(value) < 2:
            raise ValidationError("Имя должно содержать не менее 2 символов")
        self._name = value

    @property
    def email(self) -> str:
        """Адрес электронной почты."""
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        value = str(value).strip()
        if not validators.is_valid_email(value):
            raise ValidationError(f"Некорректный email: {value!r}")
        self._email = value

    @property
    def phone(self) -> str:
        """Номер телефона."""
        return self._phone

    @phone.setter
    def phone(self, value: str) -> None:
        value = str(value).strip()
        if not validators.is_valid_phone(value):
            raise ValidationError(f"Некорректный телефон: {value!r}")
        self._phone = value

    @property
    def city(self) -> str:
        """Город проживания."""
        return self._city

    @city.setter
    def city(self, value: str) -> None:
        self._city = str(value).strip()

    def contact_info(self) -> str:
        """Получить строку контактных данных.

        Returns
        -------
        str
            Строка вида ``"email | телефон"``.
        """
        return f"{self._email} | {self._phone}"

    def to_dict(self) -> dict:
        """Представить контактные данные как словарь."""
        return {
            "id": self._id,
            "name": self._name,
            "email": self._email,
            "phone": self._phone,
            "city": self._city,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Person":
        """Создать экземпляр из словаря.

        Полиморфный метод: переопределяется в подклассах.
        """
        person = cls(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            city=data.get("city", ""),
        )
        person._id = data.get("id")
        return person

    def __str__(self) -> str:
        return f"{self._name} <{self._email}>"


class Customer(Person):
    """Клиент интернет-магазина.

    Расширяет :class:`Person` характеристиками клиента: типом,
    датой регистрации и скидкой.

    Parameters
    ----------
    name : str
        Имя клиента.
    email : str
        Email клиента.
    phone : str
        Телефон клиента.
    city : str, optional
        Город клиента.
    registered : Optional[str], optional
        Дата регистрации в формате ISO ``YYYY-MM-DD``.
    """

    def __init__(
        self,
        name: str,
        email: str,
        phone: str,
        city: str = "",
        registered: Optional[str] = None,
    ) -> None:
        super().__init__(name, email, phone, city)
        self.registered = registered or date.today().isoformat()
        self._orders_count = 0

    @property
    def registered(self) -> str:
        """Дата регистрации клиента (ISO)."""
        return self._registered

    @registered.setter
    def registered(self, value: str) -> None:
        try:
            datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError as exc:
            raise ValidationError(
                f"Дата регистрации должна быть в формате ГГГГ-ММ-ДД, получено {value!r}"
            ) from exc
        self._registered = str(value)

    @property
    def orders_count(self) -> int:
        """Количество заказов клиента (агрегируется хранилищем)."""
        return self._orders_count

    @orders_count.setter
    def orders_count(self, value: int) -> None:
        self._orders_count = max(0, int(value))

    def discount(self) -> float:
        """Доля скидки клиента.

        Базовый клиент скидки не имеет (полиморфизм: переопределяется
        в подклассах).

        Returns
        -------
        float
            Величина скидки в диапазоне ``[0.0, 1.0]``.
        """
        return 0.0

    def customer_type(self) -> str:
        """Тип клиента (имя класса)."""
        return self.__class__.__name__

    def to_dict(self) -> dict:
        """Представить клиента как словарь."""
        data = super().to_dict()
        data.update(
            {
                "type": self.customer_type(),
                "registered": self._registered,
                "orders_count": self._orders_count,
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Customer":
        """Создать клиента из словаря.

        Полиморфная фабрика: по ключу ``type`` выбирает конкретный
        подкласс клиента.
        """
        customer_type = data.get("type", "Customer")
        factory: dict = {
            "Customer": Customer,
            "RegularCustomer": RegularCustomer,
            "VIPCustomer": VIPCustomer,
            "CorporateCustomer": CorporateCustomer,
        }
        klass: type = factory.get(customer_type, Customer)
        instance = klass(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            city=data.get("city", ""),
            registered=data.get("registered"),
        )
        instance._id = data.get("id")
        instance._orders_count = int(data.get("orders_count", 0) or 0)
        if isinstance(instance, VIPCustomer):
            instance.priority = data.get("priority", 1)
        if isinstance(instance, CorporateCustomer) and data.get("inn"):
            instance.inn = str(data["inn"])
        return instance


class RegularCustomer(Customer):
    """Постоянный клиент со скидкой 5 %.

    Пример наследования: расширяет :class:`Customer`
    и переопределяет полиморфный метод ``discount``.
    """

    def discount(self) -> float:
        """Величина скидки постоянного клиента (0.05)."""
        return 0.05


class VIPCustomer(Customer):
    """VIP-клиент со скидкой 15 % и приоритетом обслуживания.

    Дополнительно хранит уровень приоритета и переопределяет
    метод ``discount``.
    """

    def __init__(
        self,
        name: str,
        email: str,
        phone: str,
        city: str = "",
        registered: Optional[str] = None,
        priority: int = 1,
    ) -> None:
        super().__init__(name, email, phone, city, registered)
        self._priority = 0
        self.priority = priority

    @property
    def priority(self) -> int:
        """Приоритет обслуживания VIP-клиента (>= 1)."""
        return self._priority

    @priority.setter
    def priority(self, value: int) -> None:
        value = int(value)
        if value < 1:
            raise ValidationError("Приоритет должен быть >= 1")
        self._priority = value

    def discount(self) -> float:
        """Величина скидки VIP-клиента (0.15)."""
        return 0.15

    def to_dict(self) -> dict:
        """Словарь с дополнительным полем ``priority``."""
        data = super().to_dict()
        data["priority"] = self._priority
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "VIPCustomer":
        """Создать VIP-клиента из словаря."""
        instance = super().from_dict(data)
        instance.priority = data.get("priority", 1)
        return instance


class CorporateCustomer(Customer):
    """Корпоративный клиент (юридическое лицо).

    Хранит ИНН компании и предоставляет отсрочку платежа.
    Наследует :class:`Customer` и переопределяет ``discount``.
    """

    def __init__(
        self,
        name: str,
        email: str,
        phone: str,
        city: str = "",
        registered: Optional[str] = None,
        inn: str = "",
    ) -> None:
        super().__init__(name, email, phone, city, registered)
        self._inn = ""
        self.inn = inn

    @property
    def inn(self) -> str:
        """ИНН юридического лица."""
        return self._inn

    @inn.setter
    def inn(self, value: str) -> None:
        value = str(value).strip()
        if value and not re.fullmatch(r"\d{10}|\d{12}", value):
            raise ValidationError("ИНН должен содержать 10 или 12 цифр")
        self._inn = value

    def discount(self) -> float:
        """Величина скидки корпоративного клиента (0.10)."""
        return 0.10

    def to_dict(self) -> dict:
        """Словарь с дополнительным полем ``inn``."""
        data = super().to_dict()
        data["inn"] = self._inn
        return data


class OrderStatus(Enum):
    """Статусы жизненного цикла заказа.

    Attributes
    ----------
    NEW : OrderStatus
        Заказ создан.
    PAID : OrderStatus
        Заказ оплачен.
    SHIPPED : OrderStatus
        Заказ отправлен.
    COMPLETED : OrderStatus
        Заказ завершён.
    CANCELLED : OrderStatus
        Заказ отменён.
    """

    NEW = "новый"
    PAID = "оплачен"
    SHIPPED = "отправлен"
    COMPLETED = "завершён"
    CANCELLED = "отменён"


class OrderItem:
    """Позиция заказа: товар + количество.

    Цена фиксируется на момент добавления (снимок), чтобы
    изменение цены товара не влияло на уже созданные заказы.

    Parameters
    ----------
    product : Product
        Товар позиции.
    quantity : int
        Количество единиц товара (>= 1).
    """

    def __init__(self, product: Product, quantity: int = 1) -> None:
        self._product = product
        self._quantity = 0
        self.quantity = quantity

    @property
    def product(self) -> Product:
        """Товар позиции."""
        return self._product

    @property
    def quantity(self) -> int:
        """Количество единиц товара."""
        return self._quantity

    @quantity.setter
    def quantity(self, value: int) -> None:
        value = int(value)
        if value < 1:
            raise ValidationError("Количество товара должно быть >= 1")
        self._quantity = value

    def subtotal(self) -> float:
        """Стоимость позиции (количество * цена товара).

        Returns
        -------
        float
            Стоимость позиции.
        """
        return self._quantity * self._product.price

    def to_dict(self) -> dict:
        """Представить позицию как словарь."""
        return {
            "product_id": self._product.id,
            "product_name": self._product.name,
            "price": self._product.price,
            "quantity": self._quantity,
        }

    def __str__(self) -> str:
        return f"{self._product.name} x{self._quantity} = {self.subtotal():.2f} ₽"

    def __repr__(self) -> str:
        return f"OrderItem(product={self._product.name!r}, qty={self._quantity})"


class Order:
    """Заказ клиента.

    Содержит список позиций :class:`OrderItem`, дату создания,
    статус и ссылку на клиента. Общая стоимость вычисляется
    с учётом персональной скидки клиента.

    Parameters
    ----------
    customer : Customer
        Клиент, оформивший заказ.
    order_date : Optional[str], optional
        Дата заказа в формате ISO ``YYYY-MM-DD``.
    """

    def __init__(self, customer: Customer, order_date: Optional[str] = None) -> None:
        self._id: Optional[int] = None
        self._customer = customer
        self._order_date: str = ""
        self._status: OrderStatus = OrderStatus.NEW
        self._items: List[OrderItem] = []
        self.order_date = order_date or date.today().isoformat()

    @property
    def id(self) -> Optional[int]:
        """Уникальный идентификатор заказа."""
        return self._id

    @id.setter
    def id(self, value: Optional[int]) -> None:
        self._id = int(value) if value is not None else None

    @property
    def customer(self) -> Customer:
        """Клиент, оформивший заказ."""
        return self._customer

    @customer.setter
    def customer(self, value: Customer) -> None:
        if not isinstance(value, Customer):
            raise TypeError("Заказ может быть оформлен только клиентом")
        self._customer = value

    @property
    def order_date(self) -> str:
        """Дата заказа (ISO ``YYYY-MM-DD``)."""
        return self._order_date

    @order_date.setter
    def order_date(self, value: str) -> None:
        try:
            datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError as exc:
            raise ValidationError(
                f"Дата должна быть в формате ГГГГ-ММ-ДД, получено {value!r}"
            ) from exc
        self._order_date = str(value)

    @property
    def status(self) -> OrderStatus:
        """Текущий статус заказа."""
        return self._status

    @status.setter
    def status(self, value: OrderStatus) -> None:
        if not isinstance(value, OrderStatus):
            value = OrderStatus(str(value))
        self._status = value

    @property
    def items(self) -> Tuple[OrderItem, ...]:
        """Кортеж позиций заказа."""
        return tuple(self._items)

    def add_item(self, product: Product, quantity: int = 1) -> None:
        """Добавить позицию в заказ.

        Parameters
        ----------
        product : Product
            Добавляемый товар.
        quantity : int, optional
            Количество единиц (по умолчанию 1).
        """
        self._items.append(OrderItem(product, quantity))

    def remove_item(self, index: int) -> None:
        """Удалить позицию по индексу.

        Parameters
        ----------
        index : int
            Индекс удаляемой позиции.
        """
        try:
            self._items.pop(index)
        except IndexError as exc:
            raise ValidationError(f"Нет позиции с индексом {index}") from exc

    def total(self) -> float:
        """Суммарная стоимость заказа.

        Использует функцию :func:`sum` с лямбда-выражением для
        вычисления суммы позиций, затем применяет скидку клиента.

        Returns
        -------
        float
            Итоговая стоимость заказа с учётом скидки.
        """
        subtotal = sum(item.subtotal() for item in self._items)
        return round(subtotal * (1.0 - self._customer.discount()), 2)

    def item_count(self) -> int:
        """Общее количество единиц товара в заказе."""
        return sum(item.quantity for item in self._items)

    def set_status(self, status: OrderStatus) -> None:
        """Сменить статус заказа с проверкой допустимых переходов.

        Parameters
        ----------
        status : OrderStatus
            Новый статус заказа.
        """
        if status is order_status_allowed(self._status, status):
            self._status = status

    def to_dict(self) -> dict:
        """Представить заказ как словарь."""
        return {
            "id": self._id,
            "customer_id": self._customer.id,
            "customer_name": self._customer.name,
            "customer_type": self._customer.customer_type(),
            "order_date": self._order_date,
            "status": self._status.value,
            "total": self.total(),
            "items": [item.to_dict() for item in self._items],
        }

    @classmethod
    def from_dict(cls, data: dict, customer: Customer) -> "Order":
        """Создать заказ из словаря.

        Parameters
        ----------
        data : dict
            Словарь с ключами ``order_date``, ``status``, ``items``.
        customer : Customer
            Клиент, к которому относится заказ.

        Returns
        -------
        Order
            Новый заказ с восстановленными позициями.
        """
        order = cls(customer=customer, order_date=data.get("order_date"))
        order._id = data.get("id")
        order._status = OrderStatus(data.get("status", OrderStatus.NEW.value))
        for item in data.get("items", []):
            product = Product(
                name=item["product_name"],
                price=item["price"],
            )
            product.id = item.get("product_id")
            order.add_item(product, quantity=item["quantity"])
        return order

    def __str__(self) -> str:
        return (
            f"Заказ #{self._id} от {self._order_date} ({self._customer.name}), "
            f"{self._status.value}, итого {self.total():.2f} ₽"
        )

    def __repr__(self) -> str:
        return f"Order(id={self._id}, customer={self._customer.name!r}, total={self.total():.2f})"


def order_status_allowed(current: OrderStatus, target: OrderStatus) -> OrderStatus:
    """Проверить допустимость перехода между статусами заказа.

    Parameters
    ----------
    current : OrderStatus
        Текущий статус.
    target : OrderStatus
        Желаемый статус.

    Returns
    -------
    OrderStatus
        Желаемый статус, если переход допустим, иначе текущий.
    """
    transitions: dict = {
        OrderStatus.NEW: {OrderStatus.PAID, OrderStatus.CANCELLED},
        OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
        OrderStatus.SHIPPED: {OrderStatus.COMPLETED},
        OrderStatus.COMPLETED: set(),
        OrderStatus.CANCELLED: set(),
    }
    return target if target in transitions.get(current, set()) else current