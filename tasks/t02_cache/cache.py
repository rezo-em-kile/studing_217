"""Справочник товаров с LRU-кэшем перед медленным «внешним источником».

Запуск: python cache.py КАТАЛОГ [--size N] [--delay СЕК] < commands.txt

Встроенные словари и множества не используются: и кэш, и каталог хранятся в своей
хэш-таблице (модуль hashtable.py), порядок использования - в двусвязном списке.
"""
import math
import sys
import time

from hashtable import HashTable

DEFAULT_SIZE = 1000
DEFAULT_DELAY = 0.0
USAGE = "использование: python cache.py КАТАЛОГ [--size N] [--delay СЕК]"


class UsageError(Exception):
    """Неверные аргументы командной строки (код 2)."""


class DataError(Exception):
    """Ошибка в файле каталога (код 1)."""


class CommandError(Exception):
    """Неверная команда в диалоге: программа сообщает и продолжает работу."""


def group_digits(number):
    """12345 -> «12 345»."""
    return f"{number:,}".replace(",", " ")


class Node:
    """Элемент двусвязного списка: от самого свежего (голова) к самому давнему (хвост)."""
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """Кэш ограниченного размера: при переполнении вытесняется давно не использованная запись."""

    def __init__(self, limit):
        self.limit = limit
        self.nodes = HashTable()
        self.head = Node()
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head
        self.count = 0

    def _unlink(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _push_front(self, node):
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def lookup(self, key):
        """Значение из кэша (запись становится самой свежей) или None."""
        node = self.nodes.get(key)
        if node is None:
            return None
        self._unlink(node)
        self._push_front(node)
        return node.value

    def store(self, key, value):
        node = self.nodes.get(key)
        if node is not None:
            node.value = value
            self._unlink(node)
            self._push_front(node)
            return
        if self.count >= self.limit:
            oldest = self.tail.prev
            self._unlink(oldest)
            self.nodes.remove(oldest.key)
            self.count -= 1
        node = Node(key, value)
        self._push_front(node)
        self.nodes.insert(key, node)
        self.count += 1

    def remove(self, key):
        node = self.nodes.get(key)
        if node is None:
            return False
        self._unlink(node)
        self.nodes.remove(key)
        self.count -= 1
        return True

    def keys_recent_first(self):
        keys = []
        node = self.head.next
        while node is not self.tail:
            keys.append(node.key)
            node = node.next
        return keys


class Source:
    """«Внешний источник» - каталог из файла, каждое обращение занимает delay секунд."""

    def __init__(self, catalog, delay):
        self.catalog = catalog
        self.delay = delay

    def fetch(self, key):
        if self.delay > 0:
            time.sleep(self.delay)
        return self.catalog.get(key)


def parse_args(args):
    path = None
    size = DEFAULT_SIZE
    delay = DEFAULT_DELAY
    position = 0
    while position < len(args):
        arg = args[position]
        if arg in ("--size", "--delay"):
            if position + 1 >= len(args):
                raise UsageError(f"после {arg} нужно значение")
            value = args[position + 1]
            position += 2
            if arg == "--size":
                if not value.isascii() or not value.isdigit() or int(value) <= 0:
                    raise UsageError(f"--size: нужно целое число больше 0, получено «{value}»")
                size = int(value)
            else:
                try:
                    delay = float(value)
                except ValueError:
                    raise UsageError(f"--delay: нужно число секунд, получено «{value}»") from None
                if not math.isfinite(delay) or delay < 0:
                    raise UsageError(f"--delay: нужно число не меньше 0, получено «{value}»")
            continue
        if arg.startswith("--"):
            raise UsageError(f"неизвестный параметр {arg}")
        if path is not None:
            raise UsageError(f"лишний аргумент «{arg}»")
        path = arg
        position += 1
    if path is None:
        raise UsageError("не указан файл каталога")
    return path, size, delay


def load_catalog(path):
    try:
        with open(path, encoding="utf-8-sig") as file:
            lines = file.read().splitlines()
    except OSError as error:
        raise DataError(f"не удалось открыть файл каталога {path}: {error.strerror}") from None
    except UnicodeDecodeError:
        raise DataError(f"файл каталога {path} не в кодировке UTF-8") from None
    catalog = HashTable()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        key, separator, value = line.partition(";")
        key = key.strip()
        if not separator:
            raise DataError(f"{path}, строка {number}: нет «;» между артикулом и товаром")
        if not key:
            raise DataError(f"{path}, строка {number}: пустой артикул")
        if catalog.get(key) is not None:
            raise DataError(f"{path}, строка {number}: артикул {key} встречается повторно")
        catalog.insert(key, value.strip())
    return catalog


def execute(line, cache, source):
    """Выполняет одну команду и возвращает строку ответа."""
    parts = line.split(None, 1)
    command = parts[0]
    argument = parts[1].strip() if len(parts) > 1 else ""
    if command == "list":
        if argument:
            raise CommandError("у команды list нет параметров")
        keys = cache.keys_recent_first()
        shown = ", ".join(keys) if keys else "пусто"
        return f"Список ({group_digits(len(keys))} из {group_digits(cache.limit)}): {shown}"
    if command not in ("get", "put", "del"):
        raise CommandError(f"неизвестная команда «{command}», есть get, put, del, list")
    if command == "put":
        key, separator, value = argument.partition(";")
        key, value = key.strip(), value.strip()
        if not key:
            raise CommandError("put: не указан артикул (формат: put артикул; товар)")
        if not separator or not value:
            raise CommandError(f"put {key}: не указан товар (формат: put артикул; товар)")
        cache.store(key, value)
        return f"{key}: сохранено"
    if not argument:
        raise CommandError(f"{command}: не указан артикул")
    if command == "del":
        if cache.remove(argument):
            return f"{argument}: удалено"
        return f"{argument}: нет в кэше"
    value = cache.lookup(argument)
    if value is None:
        value = source.fetch(argument)
        if value is None:
            return f"{argument}: [товар не найден]"
        cache.store(argument, value)
    return f'{argument}: "{value}"'


def use_utf8_streams():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main():
    use_utf8_streams()
    try:
        path, size, delay = parse_args(sys.argv[1:])
    except UsageError as error:
        print(f"Ошибка: {error}; {USAGE}", file=sys.stderr)
        sys.exit(2)
    try:
        catalog = load_catalog(path)
    except DataError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        sys.exit(1)
    cache = LRUCache(size)
    source = Source(catalog, delay)
    first = True
    for raw in sys.stdin:
        line = raw.lstrip("﻿") if first else raw
        first = False
        line = line.strip()
        if not line:
            continue
        try:
            answer = execute(line, cache, source)
        except CommandError as error:
            answer = f"ОШИБКА: {error}"
        print(answer, flush=True)


if __name__ == "__main__":
    main()
