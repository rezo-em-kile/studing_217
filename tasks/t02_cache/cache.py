
import argparse
import math
import sys
import time


class Node:
    """Узел хеш-таблицы и двусвязного списка LRU."""

    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class ChainingHashTable:
    """Хеш-таблица с разрешением коллизий методом цепочек."""

    def __init__(self, capacity):
        self.buckets = [[] for _ in range(max(8, capacity * 2))]
        self.count = 0

    def _index(self, key):
        return hash(key) % len(self.buckets)

    def get(self, key):
        bucket = self.buckets[self._index(key)]

        for node in bucket:
            if node.key == key:
                return node

        return None

    def insert(self, node):
        index = self._index(node.key)
        bucket = self.buckets[index]

        for i, current in enumerate(bucket):
            if current.key == node.key:
                bucket[i] = node
                return

        bucket.append(node)
        self.count += 1

        if self.count / len(self.buckets) > 0.75:
            self._resize()

    def delete(self, key):
        index = self._index(key)
        bucket = self.buckets[index]

        for i, node in enumerate(bucket):
            if node.key == key:
                del bucket[i]
                self.count -= 1
                return node

        return None

    def _resize(self):
        old_buckets = self.buckets
        self.buckets = [[] for _ in range(len(old_buckets) * 2)]

        for bucket in old_buckets:
            for node in bucket:
                self.buckets[self._index(node.key)].append(node)


class LRUCache:
    """Кэш с вытеснением наименее используемой записи."""

    def __init__(self, capacity):
        self.capacity = capacity
        self.table = ChainingHashTable(capacity)
        self.head = None
        self.tail = None
        self.count = 0

    def _remove_node(self, node):
        if node.prev:
            node.prev.next = node.next
        else:
            self.head = node.next

        if node.next:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        node.prev = None
        node.next = None

    def _add_first(self, node):
        node.prev = None
        node.next = self.head

        if self.head:
            self.head.prev = node
        else:
            self.tail = node

        self.head = node

    def _make_recent(self, node):
        if node is self.head:
            return

        self._remove_node(node)
        self._add_first(node)

    def get(self, key):
        node = self.table.get(key)

        if node is None:
            return None

        self._make_recent(node)
        return node.value

    def put(self, key, value):
        node = self.table.get(key)

        if node is not None:
            node.value = value
            self._make_recent(node)
            return

        if self.count >= self.capacity:
            oldest = self.tail
            self._remove_node(oldest)
            self.table.delete(oldest.key)
            self.count -= 1

        node = Node(key, value)
        self.table.insert(node)
        self._add_first(node)
        self.count += 1

    def delete(self, key):
        node = self.table.delete(key)

        if node is None:
            return False

        self._remove_node(node)
        self.count -= 1
        return True

    def keys(self):
        result = []
        node = self.head

        while node is not None:
            result.append(node.key)
            node = node.next

        return result


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("ожидается целое число")

    if number <= 0:
        raise argparse.ArgumentTypeError("число должно быть больше 0")

    return number


def non_negative_float(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("ожидается число")

    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("число должно быть неотрицательным")

    return number


def load_catalog(filename):
    catalog = ChainingHashTable(1024)

    with open(filename, "r", encoding="utf-8") as file:
        for line in file:
            line = line.rstrip("\r\n")

            if not line.strip() or ";" not in line:
                continue

            key, value = line.split(";", 1)
            key = key.strip()
            value = value.strip()

            if key:
                catalog.insert(Node(key, value))

    return catalog


def format_number(number):
    return f"{number:,}".replace(",", " ")


def process_commands(cache, catalog, delay):
    for line in sys.stdin:
        line = line.strip()

        if not line:
            continue

        parts = line.split(maxsplit=1)
        command = parts[0]
        argument = parts[1].strip() if len(parts) > 1 else ""

        if command == "get":
            if not argument:
                print("ОШИБКА: пустой артикул")
                continue

            value = cache.get(argument)

            if value is None:
                if delay > 0:
                    time.sleep(delay)

                catalog_node = catalog.get(argument)
                value = (
                    catalog_node.value
                    if catalog_node is not None
                    else None
                )

                if value is None:
                    print(f"{argument}: [товар не найден]")
                    continue

                cache.put(argument, value)

            print(f'{argument}: "{value}"')

        elif command == "put":
            if ";" not in argument:
                print("ОШИБКА: требуется артикул и товар")
                continue

            key, value = argument.split(";", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                print("ОШИБКА: пустой артикул")
                continue

            if not value:
                print("ОШИБКА: пустое значение товара")
                continue

            cache.put(key, value)
            print(f"{key}: сохранено")

        elif command == "del":
            if not argument:
                print("ОШИБКА: пустой артикул")
                continue

            cache.delete(argument)
            print(f"{argument}: удалено")

        elif command == "list":
            if argument:
                print("ОШИБКА: команда list не принимает аргументы")
                continue

            keys = cache.keys()
            count = format_number(len(keys))
            capacity = format_number(cache.capacity)

            if keys:
                print(
                    f"Список ({count} из {capacity}): "
                    + ", ".join(keys)
                )
            else:
                print(f"Список (0 из {capacity}): пусто")

        else:
            print("ОШИБКА: неизвестная команда")


class FriendlyArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"Ошибка: {message}\n")


def main():
    parser = FriendlyArgumentParser()
    parser.add_argument("catalog")
    parser.add_argument("--size", type=positive_int, default=1000)
    parser.add_argument("--delay", type=non_negative_float, default=0)

    args = parser.parse_args()

    try:
        catalog = load_catalog(args.catalog)
    except (OSError, UnicodeError) as error:
        parser.error(f"не удалось прочитать каталог: {error}")

    cache = LRUCache(args.size)
    process_commands(cache, catalog, args.delay)


if __name__ == "__main__":
    main()
