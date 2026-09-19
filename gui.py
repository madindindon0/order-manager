"""Графический интерфейс пользователя (tkinter).

Класс :class:`OrderManagerApp` реализует настольное приложение
для менеджеров интернет-магазина с вкладками:

- «Клиенты» — регистрация, редактирование, удаление, поиск и
  импорт/экспорт клиентов;
- «Товары» — управление товарами и их категориями;
- «Заказы» — создание заказов с позициями, фильтрация, сортировка
  по дате/стоимости, смена статуса;
- «Аналитика» — построение отчётов (топ-5 клиентов, динамика
  заказов, продажи по товарам, граф связей) с предпросмотром.

Все операции обёрнуты в ``try/except`` с выводом сообщений об
ошибках через ``messagebox``.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

import analysis
from db import Storage, StorageError
from models import (
    Category,
    CorporateCustomer,
    Customer,
    Order,
    OrderStatus,
    Product,
    RegularCustomer,
    ValidationError,
    VIPCustomer,
)

#: Допустимые типы клиентов для формы.
CUSTOMER_TYPES = ["Обычный", "Постоянный", "VIP", "Корпоративный"]

# Тип клиента -> класс модели.
TYPE_TO_CLASS: Dict[str, type] = {
    "Обычный": Customer,
    "Постоянный": RegularCustomer,
    "VIP": VIPCustomer,
    "Корпоративный": CorporateCustomer,
}


class OrderManagerApp(tk.Tk):
    """Главное окно приложения.

    Parameters
    ----------
    storage : Storage
        Экземпляр хранилища данных.
    """

    def __init__(self, storage: Storage) -> None:
        super().__init__()
        self.storage = storage
        self.title("Система учёта заказов интернет-магазина")
        self.geometry("1280x760")
        self.minsize(1000, 620)

        self._photo_refs: List[object] = []

        self._build_toolbar()
        self._build_notebook()
        self.refresh_all()

    # ------------------------------------------------------------------
    # Сборка интерфейса
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        """Создать верхнюю панель с общими кнопками."""
        bar = ttk.Frame(self, padding=(8, 4))
        bar.pack(side="top", fill="x")
        ttk.Button(bar, text="Демо-данные", command=self._ask_seed).pack(side="left", padx=4)
        ttk.Button(bar, text="Отчёты (все)", command=self._run_reports).pack(side="left", padx=4)
        ttk.Label(bar, text="Хранилище: " + str(self.storage.path), foreground="gray").pack(side="right")

    def _build_notebook(self) -> None:
        """Создать вкладки приложения."""
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._build_clients_tab()
        self._build_products_tab()
        self._build_orders_tab()
        self._build_analytics_tab()

    # ------------------------------------------------------------------
    # Вкладка «Клиенты»
    # ------------------------------------------------------------------
    def _build_clients_tab(self) -> None:
        """Собрать вкладку управления клиентами."""
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Клиенты  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        form = ttk.LabelFrame(tab, text="Форма клиента", padding=10)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 8), pady=8)

        labels = ["Имя*", "Email*", "Телефон*", "Город", "Тип"]
        self.cl_field = {}
        for i, label in enumerate(labels):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=3)
        self.cl_name = ttk.Entry(form, width=28)
        self.cl_name.grid(row=0, column=1, pady=3)
        self.cl_email = ttk.Entry(form, width=28)
        self.cl_email.grid(row=1, column=1, pady=3)
        self.cl_phone = ttk.Entry(form, width=28)
        self.cl_phone.grid(row=2, column=1, pady=3)
        self.cl_city = ttk.Entry(form, width=28)
        self.cl_city.grid(row=3, column=1, pady=3)
        self.cl_type = ttk.Combobox(form, values=CUSTOMER_TYPES, state="readonly", width=26)
        self.cl_type.set("Обычный")
        self.cl_type.grid(row=4, column=1, pady=3)
        ttk.Label(form, text="ИНН (для юр. лица)", foreground="gray").grid(row=5, column=0, sticky="w", pady=3)
        self.cl_inn = ttk.Entry(form, width=28)
        self.cl_inn.grid(row=5, column=1, pady=3)

        btn = ttk.Frame(form)
        btn.grid(row=6, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn, text="Добавить", command=self.add_customer).pack(side="left", padx=2)
        ttk.Button(btn, text="Обновить", command=self.update_customer).pack(side="left", padx=2)
        ttk.Button(btn, text="Удалить", command=self.delete_customer).pack(side="left", padx=2)

        io = ttk.Frame(form)
        io.grid(row=7, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(io, text="Экспорт XLSX", command=lambda: self.export_dialog("clients", "xlsx")).pack(fill="x", pady=2)
        ttk.Button(io, text="Импорт XLSX", command=lambda: self.import_dialog("clients", "xlsx")).pack(fill="x", pady=2)

        right = ttk.Frame(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Поиск:").grid(row=0, column=0, sticky="w", pady=(6, 0))
        self.cl_search = ttk.Entry(right)
        self.cl_search.grid(row=0, column=1, sticky="ew", pady=(6, 0))
        self.cl_search.bind("<KeyRelease>", lambda _e: self.refresh_customers())

        cols = ("id", "name", "type", "email", "phone", "city", "orders")
        self.cl_tree = ttk.Treeview(right, columns=cols, show="headings", height=20)
        headings = {"id": "ID", "name": "Имя", "type": "Тип", "email": "Email", "phone": "Телефон", "city": "Город", "orders": "Заказов"}
        widths = {"id": 45, "name": 170, "type": 120, "email": 200, "phone": 150, "city": 140, "orders": 80}
        for col in cols:
            self.cl_tree.heading(col, text=headings[col])
            self.cl_tree.column(col, width=widths[col], anchor="w")
        self.cl_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=6)
        self.cl_tree.bind("<<TreeviewSelect>>", self._on_select_customer)

        sb = ttk.Scrollbar(right, orient="vertical", command=self.cl_tree.yview)
        sb.grid(row=1, column=2, sticky="ns", pady=6)
        self.cl_tree.configure(yscrollcommand=sb.set)

    def _on_select_customer(self, _event=None) -> None:
        """Заполнить форму данными выбранного клиента."""
        selection = self.cl_tree.selection()
        if not selection:
            return
        try:
            customer = self.storage.get_customer(int(selection[0]))
        except (ValueError, AttributeError):
            return
        if customer is None:
            return
        self.cl_name.delete(0, "end"); self.cl_name.insert(0, customer.name)
        self.cl_email.delete(0, "end"); self.cl_email.insert(0, customer.email)
        self.cl_phone.delete(0, "end"); self.cl_phone.insert(0, customer.phone)
        self.cl_city.delete(0, "end"); self.cl_city.insert(0, customer.city)
        self.cl_type.set(self._type_name(customer))
        inn = customer.inn if isinstance(customer, CorporateCustomer) else ""
        self.cl_inn.delete(0, "end"); self.cl_inn.insert(0, inn or "")

    @staticmethod
    def _type_name(customer: Customer) -> str:
        """Вернуть русское название типа клиента."""
        mapping = {
            Customer: "Обычный",
            RegularCustomer: "Постоянный",
            VIPCustomer: "VIP",
            CorporateCustomer: "Корпоративный",
        }
        return mapping.get(type(customer), "Обычный")

    # ------------------------------------------------------------------
    # Вкладка «Товары»
    # ------------------------------------------------------------------
    def _build_products_tab(self) -> None:
        """Собрать вкладку управления товарами."""
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Товары  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        form = ttk.LabelFrame(tab, text="Форма товара", padding=10)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 8), pady=8)
        ttk.Label(form, text="Название*").grid(row=0, column=0, sticky="w", pady=3)
        self.pr_name = ttk.Entry(form, width=28)
        self.pr_name.grid(row=0, column=1, pady=3)
        ttk.Label(form, text="Цена, ₽*").grid(row=1, column=0, sticky="w", pady=3)
        self.pr_price = ttk.Entry(form, width=28)
        self.pr_price.grid(row=1, column=1, pady=3)
        ttk.Label(form, text="Категория").grid(row=2, column=0, sticky="w", pady=3)
        self.pr_category = ttk.Combobox(form, width=26)
        self.pr_category.grid(row=2, column=1, pady=3)
        self.pr_category.bind("<Button-1>", lambda _e: self._refresh_categories())
        ttk.Label(form, text="Остаток").grid(row=3, column=0, sticky="w", pady=3)
        self.pr_stock = ttk.Spinbox(form, from_=0, to=100000, width=27)
        self.pr_stock.set(10)
        self.pr_stock.grid(row=3, column=1, pady=3)

        btn = ttk.Frame(form)
        btn.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn, text="Добавить", command=self.add_product).pack(side="left", padx=2)
        ttk.Button(btn, text="Обновить", command=self.update_product).pack(side="left", padx=2)
        ttk.Button(btn, text="Удалить", command=self.delete_product).pack(side="left", padx=2)

        io = ttk.Frame(form)
        io.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(io, text="Экспорт XLSX", command=lambda: self.export_dialog("products", "xlsx")).pack(fill="x", pady=2)
        ttk.Button(io, text="Импорт XLSX", command=lambda: self.import_dialog("products", "xlsx")).pack(fill="x", pady=2)

        right = ttk.Frame(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Поиск:").grid(row=0, column=0, sticky="w", pady=(6, 0))
        self.pr_search = ttk.Entry(right)
        self.pr_search.grid(row=0, column=1, sticky="ew", pady=(6, 0))
        self.pr_search.bind("<KeyRelease>", lambda _e: self.refresh_products())

        cols = ("id", "name", "price", "category", "stock")
        self.pr_tree = ttk.Treeview(right, columns=cols, show="headings", height=20)
        headings = {"id": "ID", "name": "Название", "price": "Цена, ₽", "category": "Категория", "stock": "Остаток"}
        widths = {"id": 45, "name": 280, "price": 110, "category": 180, "stock": 90}
        for col in cols:
            self.pr_tree.heading(col, text=headings[col])
            self.pr_tree.column(col, width=widths[col], anchor="w")
        self.pr_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=6)
        self.pr_tree.bind("<<TreeviewSelect>>", self._on_select_product)
        sb = ttk.Scrollbar(right, orient="vertical", command=self.pr_tree.yview)
        sb.grid(row=1, column=2, sticky="ns", pady=6)
        self.pr_tree.configure(yscrollcommand=sb.set)

    def _on_select_product(self, _event=None) -> None:
        """Заполнить форму данными выбранного товара."""
        selection = self.pr_tree.selection()
        if not selection:
            return
        product = self.storage.get_product(int(selection[0]))
        if product is None:
            return
        self.pr_name.delete(0, "end"); self.pr_name.insert(0, product.name)
        self.pr_price.delete(0, "end"); self.pr_price.insert(0, str(product.price))
        self._refresh_categories()
        self.pr_category.set(product.category.name if product.category else "")
        self.pr_stock.set(str(product.stock))

    def _refresh_categories(self) -> None:
        """Обновить список категорий в комбобоксе товара."""
        names = sorted({p.category.name for p in self.storage.products if p.category})
        self.pr_category["values"] = names

    # ------------------------------------------------------------------
    # Вкладка «Заказы»
    # ------------------------------------------------------------------
    def _build_orders_tab(self) -> None:
        """Собрать вкладку создания и управления заказами."""
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Заказы  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(tab, text="Новый заказ", padding=10)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 8), pady=8)
        ttk.Label(left, text="Клиент*").grid(row=0, column=0, sticky="w", pady=3)
        self.or_customer = ttk.Combobox(left, width=34)
        self.or_customer.grid(row=0, column=1, pady=3)
        ttk.Label(left, text="Дата (ГГГГ-ММ-ДД)").grid(row=1, column=0, sticky="w", pady=3)
        self.or_date = ttk.Entry(left, width=36)
        self.or_date.insert(0, date.today().isoformat())
        self.or_date.grid(row=1, column=1, pady=3)
        ttk.Label(left, text="Статус").grid(row=2, column=0, sticky="w", pady=3)
        self.or_status = ttk.Combobox(left, values=[s.value for s in OrderStatus], state="readonly", width=34)
        self.or_status.set(OrderStatus.NEW.value)
        self.or_status.grid(row=2, column=1, pady=3)

        items = ttk.LabelFrame(left, text="Позиции заказа", padding=6)
        items.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        items.columnconfigure(1, weight=1)
        ttk.Label(items, text="Товар").grid(row=0, column=0, sticky="w", pady=2)
        self.or_product = ttk.Combobox(items, width=36)
        self.or_product.grid(row=0, column=1, pady=2)
        ttk.Label(items, text="Кол-во").grid(row=1, column=0, sticky="w", pady=2)
        self.or_qty = ttk.Spinbox(items, from_=1, to=100, width=34)
        self.or_qty.set(1)
        self.or_qty.grid(row=1, column=1, pady=2)
        ttk.Button(items, text="Добавить позицию", command=self._add_order_item).grid(
            row=2, column=0, columnspan=2, pady=6, sticky="ew"
        )
        self.or_items_list = tk.Listbox(items, height=6)
        self.or_items_list.grid(row=3, column=0, columnspan=2, sticky="ew", pady=4)
        self.or_items_list.insert("end", "(позиции пока не добавлены)")

        btn = ttk.Frame(left, padding=(0, 6))
        btn.grid(row=4, column=0, columnspan=2, sticky="ew")
        ttk.Button(btn, text="Создать заказ", command=self.add_order).pack(fill="x")
        ttk.Button(btn, text="Очистить форму", command=self._reset_order_form).pack(fill="x", pady=(4, 0))

        right = ttk.Frame(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        filters = ttk.Frame(right)
        filters.grid(row=0, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(filters, text="Поиск:").pack(side="left")
        self.or_search = ttk.Entry(filters, width=22)
        self.or_search.pack(side="left", padx=4)
        self.or_search.bind("<KeyRelease>", lambda _e: self.refresh_orders())
        ttk.Label(filters, text="Статус:").pack(side="left", padx=(10, 0))
        self.or_filter_status = ttk.Combobox(
            filters, values=["Все"] + [s.value for s in OrderStatus], state="readonly", width=12
        )
        self.or_filter_status.set("Все")
        self.or_filter_status.pack(side="left", padx=4)
        self.or_filter_status.bind("<<ComboboxSelected>>", lambda _e: self.refresh_orders())
        ttk.Label(filters, text="Сортировка:").pack(side="left", padx=(10, 0))
        self.or_sort = ttk.Combobox(
            filters,
            values=["дата ↑", "дата ↓", "стоимость ↑", "стоимость ↓"],
            state="readonly",
            width=13,
        )
        self.or_sort.set("дата ↑")
        self.or_sort.pack(side="left", padx=4)
        self.or_sort.bind("<<ComboboxSelected>>", lambda _e: self.refresh_orders())

        cols = ("id", "date", "customer", "items", "status", "total")
        self.or_tree = ttk.Treeview(right, columns=cols, show="headings", height=18)
        headings = {"id": "№", "date": "Дата", "customer": "Клиент", "items": "Позиций", "status": "Статус", "total": "Итого, ₽"}
        widths = {"id": 45, "date": 95, "customer": 200, "items": 70, "status": 95, "total": 110}
        for col in cols:
            self.or_tree.heading(col, text=headings[col])
            self.or_tree.column(col, width=widths[col], anchor="w")
        self.or_tree.grid(row=1, column=0, sticky="nsew", pady=6)
        self.or_tree.bind("<<TreeviewSelect>>", self._on_select_order)
        sb = ttk.Scrollbar(right, orient="vertical", command=self.or_tree.yview)
        sb.grid(row=1, column=1, sticky="ns", pady=6)
        self.or_tree.configure(yscrollcommand=sb.set)

        bottom = ttk.Frame(right)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Label(bottom, text="Статус выбранного заказа:").pack(side="left")
        self.or_change_status = ttk.Combobox(
            bottom, values=[s.value for s in OrderStatus], state="readonly", width=12
        )
        self.or_change_status.pack(side="left", padx=4)
        ttk.Button(bottom, text="Применить статус", command=self.change_order_status).pack(side="left", padx=4)
        ttk.Button(bottom, text="Удалить заказ", command=self.delete_order).pack(side="left", padx=4)
        ttk.Button(bottom, text="Экспорт XLSX", command=lambda: self.export_dialog("orders", "xlsx")).pack(side="right", padx=2)
        ttk.Button(bottom, text="Импорт XLSX", command=lambda: self.import_dialog("orders", "xlsx")).pack(side="right", padx=2)

    # ------------------------------------------------------------------
    # Вкладка «Аналитика»
    # ------------------------------------------------------------------
    def _build_analytics_tab(self) -> None:
        """Собрать вкладку анализа и визуализации данных."""
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Аналитика  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        panel = ttk.LabelFrame(tab, text="Отчёты", padding=10)
        panel.grid(row=0, column=0, sticky="ns", pady=8)
        reports = [
            ("Топ-5 клиентов", self._report_top),
            ("Динамика заказов", self._report_dynamics),
            ("Продажи по товарам", self._report_sales),
            ("Граф связей клиентов", self._report_graph),
            ("Все отчёты", self._run_reports),
        ]
        for text, command in reports:
            ttk.Button(panel, text=text, command=command).pack(fill="x", pady=3)

        self.an_report_dir = ttk.Entry(panel)
        self.an_report_dir.insert(0, "reports")
        self.an_report_dir.pack(fill="x", pady=(10, 0))
        ttk.Button(panel, text="Открыть папку с отчётами", command=self._open_reports_dir).pack(fill="x", pady=3)

        preview = ttk.Frame(tab)
        preview.grid(row=0, column=1, sticky="nsew", pady=8)
        preview.rowconfigure(1, weight=1)
        preview.columnconfigure(0, weight=1)
        ttk.Label(preview, text="Предпросмотр отчёта").pack()
        self.an_image_label = ttk.Label(preview, text="Выберите отчёт слева", anchor="center")
        self.an_image_label.pack(fill="both", expand=True, padx=6, pady=6)

    # ------------------------------------------------------------------
    # Действия: клиенты
    # ------------------------------------------------------------------
    def add_customer(self) -> None:
        """Добавить клиента из формы."""
        try:
            customer = self._customer_from_form()
            self.storage.add_customer(customer)
            messagebox.showinfo("Готово", f"Клиент «{customer.name}» добавлен (id={customer.id})")
            self._clear_customer_form()
            self.refresh_customers()
        except (ValidationError, TypeError, ValueError, StorageError) as exc:
            messagebox.showerror("Ошибка", str(exc))

    def update_customer(self) -> None:
        """Обновить выбранного клиента."""
        selection = self.cl_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите клиента в списке")
            return
        try:
            customer = self._customer_from_form()
            customer.id = int(selection[0])
            self.storage.update_customer(customer)
            self.refresh_customers()
        except (ValidationError, TypeError, ValueError, StorageError) as exc:
            messagebox.showerror("Ошибка", str(exc))

    def delete_customer(self) -> None:
        """Удалить выбранного клиента (с его заказами)."""
        selection = self.cl_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите клиента в списке")
            return
        if not messagebox.askyesno("Удаление", "Удалить клиента и его заказы?"):
            return
        try:
            self.storage.delete_customer(int(selection[0]))
            self.refresh_all()
        except StorageError as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _customer_from_form(self) -> Customer:
        """Собрать объект клиента из полей формы.

        Raises
        ------
        ValidationError
            Если одно из полей не прошло валидацию.
        """
        klass = TYPE_TO_CLASS[self.cl_type.get()]
        kwargs = {
            "name": self.cl_name.get(),
            "email": self.cl_email.get(),
            "phone": self.cl_phone.get(),
            "city": self.cl_city.get(),
        }
        if klass is VIPCustomer:
            return klass(**kwargs, priority=1)
        if klass is CorporateCustomer:
            return klass(**kwargs, inn=self.cl_inn.get())
        return klass(**kwargs)

    def _clear_customer_form(self) -> None:
        """Очистить поля формы клиента."""
        for entry in (self.cl_name, self.cl_email, self.cl_phone, self.cl_city, self.cl_inn):
            entry.delete(0, "end")
        self.cl_type.set("Обычный")

    # ------------------------------------------------------------------
    # Действия: товары
    # ------------------------------------------------------------------
    def add_product(self) -> None:
        """Добавить товар из формы."""
        try:
            product = self._product_from_form()
            self.storage.add_product(product)
            messagebox.showinfo("Готово", f"Товар «{product.name}» добавлен")
            self._clear_product_form()
            self.refresh_products()
        except (ValidationError, TypeError, ValueError) as exc:
            messagebox.showerror("Ошибка", str(exc))

    def update_product(self) -> None:
        """Обновить выбранный товар."""
        selection = self.pr_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите товар в списке")
            return
        try:
            product = self._product_from_form()
            product.id = int(selection[0])
            self.storage.update_product(product)
            self.refresh_products()
        except (ValidationError, TypeError, ValueError, StorageError) as exc:
            messagebox.showerror("Ошибка", str(exc))

    def delete_product(self) -> None:
        """Удалить выбранный товар."""
        selection = self.pr_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите товар в списке")
            return
        try:
            self.storage.delete_product(int(selection[0]))
            self.refresh_products()
        except StorageError as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _product_from_form(self) -> Product:
        """Собрать объект товара из полей формы."""
        category_name = self.pr_category.get().strip()
        category = Category(category_name) if category_name else None
        return Product(
            name=self.pr_name.get(),
            price=float(self.pr_price.get()),
            category=category,
            stock=int(self.pr_stock.get() or 0),
        )

    def _clear_product_form(self) -> None:
        """Очистить поля формы товара."""
        self.pr_name.delete(0, "end")
        self.pr_price.delete(0, "end")
        self.pr_category.set("")
        self.pr_stock.set(10)

    # ------------------------------------------------------------------
    # Действия: заказы
    # ------------------------------------------------------------------
    def _reset_order_form(self) -> None:
        """Сбросить форму создания заказа."""
        self.or_customer.set("")
        self.or_date.delete(0, "end")
        self.or_date.insert(0, date.today().isoformat())
        self.or_status.set(OrderStatus.NEW.value)
        self.or_qty.set(1)
        self.or_product.set("")
        self.or_items_list.delete(0, "end")
        self.or_items_list.insert("end", "(позиции пока не добавлены)")

    def _add_order_item(self) -> None:
        """Добавить выбранный товар в список позиций заказа."""
        try:
            product = self._selected_product()
            qty = int(self.or_qty.get())
            item = f"{product.name} x{qty} = {qty * product.price:.2f} ₽"
            if self.or_items_list.get(0) == "(позиции пока не добавлены)":
                self.or_items_list.delete(0)
            self.or_items_list.insert("end", item)
        except (ValueError, AttributeError) as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _selected_product(self) -> Product:
        """Найти товар, выбранный в комбобоксе заказа."""
        name = self.or_product.get()
        for product in self.storage.products:
            if product.name == name:
                return product
        raise ValueError("Выберите товар из списка")

    def add_order(self) -> None:
        """Создать заказ из формы."""
        try:
            customer = self._selected_customer()
            order = Order(customer=customer, order_date=self.or_date.get() or None)
            order.status = OrderStatus(self.or_status.get())
            for line_index in range(self.or_items_list.size()):
                line = self.or_items_list.get(line_index)
                product = self._product_from_line(line)
                quantity = self._quantity_from_line(line)
                order.add_item(product, quantity)
            if not order.items:
                raise ValidationError("Добавьте хотя бы одну позицию в заказ")
            self.storage.add_order(order)
            messagebox.showinfo("Готово", f"Заказ №{order.id} создан, сумма {order.total():.2f} ₽")
            self._reset_order_form()
            self.refresh_orders()
            self.refresh_customers()
        except (ValidationError, TypeError, ValueError, StorageError) as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _product_from_line(self, line: str) -> Product:
        """Извлечь товар из строки списка позиций (до `` x``).

        Цена берётся из актуального товара в хранилище, чтобы
        в заказ попадала реальная стоимость, а не ноль.
        """
        name = line.rsplit(" x", 1)[0]
        for product in self.storage.products:
            if product.name == name:
                return product
        return Product(name=name, price=0.0)

    def _quantity_from_line(self, line: str) -> int:
        """Извлечь количество из строки списка позиций."""
        import re

        match = re.search(r"x(\d+)", line)
        return int(match.group(1)) if match else 1

    def _selected_customer(self) -> Customer:
        """Найти клиента по выбору в комбобоксе заказа."""
        value = self.or_customer.get()
        if not value:
            raise ValidationError("Выберите клиента")
        customer_id = int(value.split(" ")[1].rstrip("—").strip() or value.split(" ")[0])
        return self.storage.get_customer(customer_id) or self._find_customer_by_name(value)

    def _find_customer_by_name(self, name: str) -> Customer:
        """Найти клиента по имени."""
        for customer in self.storage.customers:
            if customer.name in name or name in customer.name:
                return customer
        raise ValidationError("Клиент не найден")

    def _on_select_order(self, _event=None) -> None:
        """Показать статус выбранного заказа в поле смены статуса."""
        selection = self.or_tree.selection()
        if not selection:
            return
        self.or_change_status.set(self.storage.get_order(int(selection[0])).status.value)

    def change_order_status(self) -> None:
        """Сменить статус выбранного заказа (с проверкой переходов)."""
        selection = self.or_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите заказ в списке")
            return
        try:
            order = self.storage.get_order(int(selection[0]))
            target = OrderStatus(self.or_change_status.get())
            new_status = messagebox_status_order(order.status, target)
            order.status = new_status
            self.storage.update_order(order)
            self.refresh_orders()
        except (ValueError, StorageError) as exc:
            messagebox.showerror("Ошибка", str(exc))

    def delete_order(self) -> None:
        """Удалить выбранный заказ."""
        selection = self.or_tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите заказ в списке")
            return
        if not messagebox.askyesno("Удаление", "Удалить заказ?"):
            return
        try:
            self.storage.delete_order(int(selection[0]))
            self.refresh_orders()
            self.refresh_customers()
        except StorageError as exc:
            messagebox.showerror("Ошибка", str(exc))

    # ------------------------------------------------------------------
    # Аналитика
    # ------------------------------------------------------------------
    def _report_top(self) -> None:
        """Построить отчёт «Топ клиентов по числу заказов»."""
        self._show_report(analysis.plot_top_customers(analysis.top_customers(self.storage.orders)))

    def _report_dynamics(self) -> None:
        """Построить отчёт «Динамика заказов»."""
        self._show_report(analysis.plot_orders_dynamics(analysis.orders_dynamics(self.storage.orders)))

    def _report_sales(self) -> None:
        """Построить отчёт «Продажи по товарам»."""
        self._show_report(analysis.plot_sales_by_category(analysis.sales_by_category(self.storage.orders)))

    def _report_graph(self) -> None:
        """Построить отчёт «Граф связей клиентов»."""
        graph = analysis.build_customer_graph(self.storage.customers, self.storage.orders)
        self._show_report(analysis.plot_customer_graph(graph))

    def _run_reports(self) -> None:
        """Построить все отчёты и показать первый из них."""
        try:
            dest = Path(self.an_report_dir.get().strip() or "reports")
            dest.mkdir(parents=True, exist_ok=True)
            paths = analysis.run_all_reports(self.storage.customers, self.storage.orders, dest)
            self._show_report(paths["top_customers"])
            messagebox.showinfo("Готово", "Все отчёты сформированы\n" + "\n".join(str(p) for p in paths.values()))
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось построить отчёты:\n{exc}")

    def _show_report(self, path: str | Path) -> None:
        """Показать PNG-отчёт в области предпросмотра.

        Parameters
        ----------
        path : str | Path
            Путь к PNG-файлу отчёта.
        """
        try:
            from PIL import Image, ImageTk

            image = Image.open(path)
            image.thumbnail((1000, 560))
            photo = ImageTk.PhotoImage(image)
            self._photo_refs.append(photo)
            self.an_image_label.config(image=photo, text="")
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть изображение:\n{exc}")

    def _open_reports_dir(self) -> None:
        """Открыть каталог с отчётами в файловом менеджере."""
        dest = Path(self.an_report_dir.get().strip() or "reports")
        dest.mkdir(parents=True, exist_ok=True)
        filedialog.askdirectory(initialdir=dest)

    # ------------------------------------------------------------------
    # Импорт / экспорт
    # ------------------------------------------------------------------
    def export_dialog(self, entity: str, fmt: str) -> None:
        """Экспортировать сущность, выбрав каталог назначения."""
        dest = filedialog.askdirectory(title="Куда экспортировать?")
        if not dest:
            return
        try:
            path = getattr(self.storage, f"export_{fmt}")(entity, dest)
            messagebox.showinfo("Готово", f"Экспортировано: {path}")
        except StorageError as exc:
            messagebox.showerror("Ошибка", str(exc))

    def import_dialog(self, entity: str, fmt: str) -> None:
        """Импортировать сущность из файла (XLSX)."""
        filetypes = [("Excel", "*.xlsx")]
        path = filedialog.askopenfilename(title="Выберите файл", filetypes=filetypes)
        if not path:
            return
        try:
            count = getattr(self.storage, f"import_{fmt}")(entity, path)
            messagebox.showinfo("Готово", f"Импортировано записей: {count}")
            self.refresh_all()
        except (StorageError, ValidationError) as exc:
            messagebox.showerror("Ошибка", str(exc))

    # ------------------------------------------------------------------
    # Обновление списков
    # ------------------------------------------------------------------
    def refresh_all(self) -> None:
        """Обновить все вкладки приложения."""
        self.refresh_products()
        self.refresh_customers()
        self.refresh_orders()

    def refresh_customers(self) -> None:
        """Обновить таблицу клиентов с учётом поиска."""
        query = self.cl_search.get().strip().lower()
        self.cl_tree.delete(*self.cl_tree.get_children())
        for customer in self.storage.customers:
            haystack = f"{customer.name} {customer.email} {customer.phone} {customer.city}".lower()
            if query and query not in haystack:
                continue
            self.cl_tree.insert(
                "",
                "end",
                iid=str(customer.id),
                values=(
                    customer.id,
                    customer.name,
                    self._type_name(customer),
                    customer.email,
                    customer.phone,
                    customer.city,
                    customer.orders_count,
                ),
            )
        # Выпадающий список клиентов в форме заказа — из всех клиентов базы,
        # а не только из тех, у кого уже есть заказы.
        self.or_customer["values"] = sorted(
            {f"{c.id} — {c.name}" for c in self.storage.customers},
            key=lambda s: int(s.split(" ")[0]),
        )

    def refresh_products(self) -> None:
        """Обновить таблицу товаров с учётом поиска."""
        query = self.pr_search.get().strip().lower()
        self.pr_tree.delete(*self.pr_tree.get_children())
        for product in self.storage.products:
            haystack = f"{product.name} {product.category.name if product.category else ''}".lower()
            if query and query not in haystack:
                continue
            self.pr_tree.insert(
                "",
                "end",
                iid=str(product.id),
                values=(
                    product.id,
                    product.name,
                    f"{product.price:.2f}",
                    product.category.name if product.category else "",
                    product.stock,
                ),
            )
        # Выпадающий список товаров в форме заказа — из всех товаров базы.
        self.or_product["values"] = sorted(p.name for p in self.storage.products)

    def refresh_orders(self) -> None:
        """Обновить таблицу заказов с учётом фильтров и сортировки."""
        query = self.or_search.get().strip().lower()
        status_filter = self.or_filter_status.get()
        self.or_tree.delete(*self.or_tree.get_children())

        orders = list(self.storage.orders)
        by = "date"
        reverse = False
        if self.or_sort.get() == "дата ↓":
            reverse = True
        elif self.or_sort.get() == "стоимость ↑":
            by = "total"
        elif self.or_sort.get() == "стоимость ↓":
            by, reverse = "total", True
        orders = analysis.sort_orders(orders, by=by, reverse=reverse)

        for order in orders:
            if query and query not in f"{order.customer.name} {order.id}".lower():
                continue
            if status_filter != "Все" and order.status.value != status_filter:
                continue
            self.or_tree.insert(
                "",
                "end",
                iid=str(order.id),
                values=(
                    order.id,
                    order.order_date,
                    order.customer.name,
                    order.item_count(),
                    order.status.value,
                    f"{order.total():.2f}",
                ),
            )

    def _ask_seed(self) -> None:
        """Перезаполнить хранилище демонстрационными данными."""
        if messagebox.askyesno("Демо-данные", "Заменить все данные демонстрационным набором?"):
            try:
                self.storage.seed_demo_data()
                self.refresh_all()
                messagebox.showinfo("Готово", "Демо-данные загружены")
            except Exception as exc:
                messagebox.showerror("Ошибка", str(exc))


def messagebox_status_order(current_status, target_status):
    """Проверить переход статуса и выдать предупреждение при запрете."""
    from models import order_status_allowed

    allowed = order_status_allowed(current_status, target_status)
    if allowed is not target_status:
        messagebox.showwarning(
            "Переход запрещён",
            f"Переход из статуса «{current_status.value}» в «{target_status.value}» недопустим",
        )
    return allowed


def run_app(storage: Storage) -> None:
    """Запустить графическое приложение.

    Parameters
    ----------
    storage : Storage
        Хранилище данных приложения.
    """
    app = OrderManagerApp(storage)
    app.mainloop()