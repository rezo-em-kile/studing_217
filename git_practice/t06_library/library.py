"""Учёт книг в библиотеке: выдача, возврат, штрафы за просрочку.

Дни считаются целыми числами (номер дня от начала года). Книгу выдают на LOAN_DAYS дней:
взятую в день 1 нужно вернуть не позже дня 15. За каждый день просрочки - штраф FINE_PER_DAY.

    python library.py samples/catalog.txt
"""
from __future__ import annotations

import sys

LOAN_DAYS = 14          # срок выдачи, дней
FINE_PER_DAY = 10       # штраф за день просрочки, руб.


class LibraryError(Exception):
    """Ошибка операции с библиотекой."""


class Library:
    def __init__(self):
        self._titles = {}        # isbn → название
        self._copies = {}        # isbn → всего экземпляров
        self._loans = {}         # (isbn, читатель) → день выдачи

    def add_book(self, isbn, title, copies=1):
        """Добавить книгу; повторный ISBN с тем же названием добавляет экземпляры."""
        if copies < 1:
            raise LibraryError("число экземпляров должно быть больше нуля")
        if isbn in self._titles and self._titles[isbn] != title:
            raise LibraryError(f"ISBN {isbn} уже занят книгой «{self._titles[isbn]}»")
        self._titles[isbn] = title
        self._copies[isbn] = self._copies.get(isbn, 0) + copies

    def title(self, isbn):
        self._check(isbn)
        return self._titles[isbn]

    def available(self, isbn):
        self._check(isbn)
        on_loan = sum(1 for book, _ in self._loans if book == isbn)
        return self._copies[isbn] - on_loan

    def find(self, query):
        query = query.strip()
        return sorted(isbn for isbn, title in self._titles.items() if query in title.lower())

    def borrow(self, isbn, reader, day):
        if self.available(isbn) <= 0:
            raise LibraryError(f"нет свободных экземпляров «{self._titles[isbn]}»")
        if (isbn, reader) in self._loans:
            raise LibraryError(f"{reader} уже взял «{self._titles[isbn]}»")
        self._loans[(isbn, reader)] = day

    def return_book(self, isbn, reader, day):
        if (isbn, reader) not in self._loans:
            raise LibraryError(f"{reader} не брал книгу {isbn}")
        start = self._loans[(isbn, reader)]
        if day < start:
            raise LibraryError(f"день возврата {day} раньше дня выдачи {start}")
        del self._loans[(isbn, reader)]
        overdue = day - start - LOAN_DAYS
        return max(overdue, 0) * FINE_PER_DAY

    def loans_of(self, reader):
        """Книги, которые сейчас у читателя."""
        return sorted(isbn for isbn, who in self._loans if who == reader)

    def _check(self, isbn):
        if isbn not in self._titles:
            raise LibraryError(f"нет книги с ISBN {isbn}")


def load_catalog(lines):
    library = Library()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(";")]
        if len(parts) != 3 or not parts[2].isdigit():
            raise LibraryError(f"строка {number}: ожидается «ISBN; название; экземпляров»")
        library.add_book(parts[0], parts[1], int(parts[2]))
    return library


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Запуск: python library.py каталог.txt", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as file:
            library = load_catalog(file)
    except (OSError, LibraryError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    for isbn in library.find(""):
        print(f"{isbn}  {library.title(isbn)} - свободно: {library.available(isbn)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
