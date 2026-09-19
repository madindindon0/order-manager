"""Unit-тесты слоя хранения :mod:`db`.

Покрывают запрет создания нескольких клиентов с одинаковым email
или номером телефона (уникальность контактов) при добавлении,
обновлении и импорте.

Запуск::

    python -m unittest tests.test_db -v
"""

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from db import Storage, StorageError
from models import Customer


def make_customer(**kwargs):
    """Создать клиента с разумными значениями по умолчанию."""
    defaults = {
        "name": "Иван Петров",
        "email": "ivan@example.com",
        "phone": "+7 (900) 123-45-67",
    }
    defaults.update(kwargs)
    return Customer(**defaults)


class CustomerUniquenessTest(unittest.TestCase):
    """Проверка уникальности email и телефона клиентов."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self._tmp.name) / "store.xlsx")

    def tearDown(self):
        self._tmp.cleanup()

    def test_add_with_unique_contacts(self):
        first = self.storage.add_customer(make_customer())
        second = self.storage.add_customer(
            make_customer(email="petr@example.com", phone="+7 (911) 222-33-44")
        )
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(self.storage.customers), 2)

    def test_duplicate_email_rejected(self):
        self.storage.add_customer(make_customer())
        with self.assertRaises(StorageError):
            self.storage.add_customer(make_customer(email="ivan@example.com"))

    def test_duplicate_email_case_insensitive(self):
        self.storage.add_customer(make_customer())
        for email in ("IVAN@EXAMPLE.COM", "Ivan@Example.com", "IVAN@example.com"):
            with self.subTest(email=email):
                with self.assertRaises(StorageError):
                    self.storage.add_customer(make_customer(email=email))

    def test_duplicate_phone_rejected(self):
        self.storage.add_customer(make_customer())
        with self.assertRaises(StorageError):
            self.storage.add_customer(make_customer(phone="+7 (900) 123-45-67"))

    def test_duplicate_phone_in_other_format(self):
        # Разные форматы одного номера считаются дубликатами.
        self.storage.add_customer(make_customer(phone="+7 (900) 123-45-67"))
        for phone in ("+79001234567", "8 900 123 45 67", "89001234567"):
            with self.subTest(phone=phone):
                with self.assertRaises(StorageError):
                    self.storage.add_customer(make_customer(phone=phone))

    def test_same_person_added_twice_rejected(self):
        # Добавление клиента с теми же контактами (email и/или телефон)
        # должно отклоняться — дубликат по каждому полю отдельно.
        self.storage.add_customer(make_customer())
        with self.assertRaises(StorageError):
            self.storage.add_customer(make_customer())

    def test_update_with_same_contact_allowed(self):
        customer = self.storage.add_customer(make_customer())
        updated = make_customer(city="Казань", name="Иван Петрович")
        updated.id = customer.id
        # Обновление без смены контактов не считается дубликатом.
        self.storage.update_customer(updated)
        self.assertEqual(len(self.storage.customers), 1)

    def test_update_to_duplicate_email_rejected(self):
        first = self.storage.add_customer(make_customer())
        self.storage.add_customer(
            make_customer(email="petr@example.com", phone="+7 (911) 222-33-44")
        )
        updated = make_customer()
        updated.id = first.id
        updated.email = "petr@example.com"
        with self.assertRaises(StorageError):
            self.storage.update_customer(updated)

    def test_update_to_duplicate_phone_rejected(self):
        first = self.storage.add_customer(make_customer())
        self.storage.add_customer(
            make_customer(email="petr@example.com", phone="+7 (911) 222-33-44")
        )
        updated = make_customer()
        updated.id = first.id
        updated.phone = "+7 (911) 222-33-44"
        with self.assertRaises(StorageError):
            self.storage.update_customer(updated)

    def test_duplicate_persists_after_reload(self):
        # Дубликат, попавший в файл вручную, не блокирует загрузку,
        # но повторное добавление тех же контактов отклоняется.
        path = self._tmp.name
        self.storage.add_customer(make_customer())
        reloaded = Storage(Path(path) / "store.xlsx")
        with self.assertRaises(StorageError):
            reloaded.add_customer(make_customer())

    def test_import_rejects_duplicate_email(self):
        self.storage.add_customer(make_customer())
        wb = Workbook()
        ws = wb.active
        ws.append(["id", "type", "name", "email", "phone", "city", "registered", "orders_count", "inn", "priority"])
        ws.append([None, "Customer", "Дубликат", "ivan@example.com", "+7 (900) 123-45-67", "", "", 0, "", ""])
        import_path = Path(self._tmp.name) / "import.xlsx"
        wb.save(import_path)
        try:
            with self.assertRaises(StorageError):
                self.storage.import_xlsx("clients", import_path)
        finally:
            wb.close()


if __name__ == "__main__":
    unittest.main()