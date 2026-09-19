"""Валидация контактных данных с помощью регулярных выражений.

Модуль содержит проверки адреса электронной почты и номера
телефона на основе модуля :mod:`re`. Функции используются
моделями (см. :mod:`models`) и слоем GUI.

Пример использования::

    >>> import validators
    >>> validators.is_valid_email("ivan@example.com")
    True
    >>> validators.is_valid_phone("+7 (900) 123-45-67")
    True
"""

from __future__ import annotations

import re

#: Допустимый формат адреса электронной почты.
#: Локальная часть: буквы, цифры и символы ``._%+-``;
#: домен: метки из букв/цифр/дефисов, разделённые точками;
#: последняя метка — не менее двух букв.
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)

#: Допустимый формат российского номера телефона.
#: Необязательный код страны ``+7`` или ``8``, затем 10 цифр,
#: допускаются пробелы, скобки и дефисы как разделители.
PHONE_PATTERN = re.compile(
    r"^(?:\+7|8)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$"
)

#: Шаблон для извлечения только цифр из номера телефона.
DIGITS_PATTERN = re.compile(r"\D")


def is_valid_email(email: str) -> bool:
    """Проверить корректность адреса электронной почты.

    Parameters
    ----------
    email : str
        Проверяемый адрес электронной почты.

    Returns
    -------
    bool
        ``True``, если адрес соответствует шаблону
        :data:`EMAIL_PATTERN`, иначе ``False``.

    Examples
    --------
    >>> is_valid_email("user@example.com")
    True
    >>> is_valid_email("bad-address")
    False
    """
    return bool(EMAIL_PATTERN.fullmatch(str(email).strip()))


def is_valid_phone(phone: str) -> bool:
    """Проверить корректность номера телефона.

    Принимаются номера вида ``+7 (900) 123-45-67``, ``89001234567``
    и ``8 900 123 45 67``.

    Parameters
    ----------
    phone : str
        Проверяемый номер телефона.

    Returns
    -------
    bool
        ``True``, если номер соответствует шаблону
        :data:`PHONE_PATTERN`, иначе ``False``.

    Examples
    --------
    >>> is_valid_phone("+7 (900) 123-45-67")
    True
    >>> is_valid_phone("123")
    False
    """
    return bool(PHONE_PATTERN.fullmatch(str(phone).strip()))


def normalize_phone(phone: str) -> str:
    """Привести номер телефона к каноническому виду ``+7XXXXXXXXXX``.

    Извлекает из номера только цифры и заменяет ведущую 8 на +7.

    Parameters
    ----------
    phone : str
        Номер телефона в произвольном формате.

    Returns
    -------
    str
        Номер в каноническом виде.

    Examples
    --------
    >>> normalize_phone("8 (900) 123-45-67")
    '+79001234567'
    """
    digits = DIGITS_PATTERN.sub("", str(phone).strip())
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return "+" + digits if digits else "+"