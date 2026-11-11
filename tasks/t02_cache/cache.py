import math
import sys
import time
from typing import Optional


class Node:
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value
        self.prev: Optional["Node"] = None
        self.next: Optional["Node"] = None


class ChainingMap:
    """Собственная хэш-таблица на методе цепочек (без использования встроенного dict)."""

    def __init__(self, initial_buckets: int = 16):
        self.num_buckets = initial_buckets
        self.size = 0
        self.buckets: list[list[tuple[str, str]]] = [[] for _ in range(self.num_buckets)]

    def _bucket_idx(self, key: str) -> int:
        return hash(key) & (self.num_buckets - 1)

    def _resize(self) -> None:
        old_buckets = self.buckets
        self.num_buckets *= 2
        self.buckets = [[] for _ in range(self.num_buckets)]
        self.size = 0
        for bucket in old_buckets:
            for k, v in bucket:
                self.set(k, v)

    def set(self, key: str, value: str) -> None:
        idx = self._bucket_idx(key)
        bucket = self.buckets[idx]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)
                return
        bucket.append((key, value))
        self.size += 1
        if self.size > self.num_buckets * 0.75:
            self._resize()

    def get(self, key: str) -> Optional[str]:
        idx = self._bucket_idx(key)
        for k, v in self.buckets[idx]:
            if k == key:
                return v
        return None

    def contains(self, key: str) -> bool:
        return self.get(key) is not None


class ChainingLRUCache:
    """LRU-кэш на базе хэш-таблицы с цепочками и двусвязного списка."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.size = 0
        self.num_buckets = max(16, 1 << (capacity * 2 - 1).bit_length())
        self.buckets: list[list[tuple[str, Node]]] = [[] for _ in range(self.num_buckets)]

        self.head = Node("", "")
        self.tail = Node("", "")
        self.head.next = self.tail
        self.tail.prev = self.head

    def _bucket_index(self, key: str) -> int:
        return hash(key) & (self.num_buckets - 1)

    def _remove_node(self, node: Node) -> None:
        prev_node = node.prev
        next_node = node.next
        if prev_node is not None and next_node is not None:
            prev_node.next = next_node
            next_node.prev = prev_node

    def _add_to_front(self, node: Node) -> None:
        first = self.head.next
        node.prev = self.head
        node.next = first
        self.head.next = node
        if first is not None:
            first.prev = node

    def get(self, key: str) -> Optional[str]:
        idx = self._bucket_index(key)
        for k, node in self.buckets[idx]:
            if k == key:
                self._remove_node(node)
                self._add_to_front(node)
                return node.value
        return None

    def put(self, key: str, value: str) -> None:
        idx = self._bucket_index(key)
        bucket = self.buckets[idx]
        for k, node in bucket:
            if k == key:
                node.value = value
                self._remove_node(node)
                self._add_to_front(node)
                return

        if self.size >= self.capacity:
            lru = self.tail.prev
            if lru is not None and lru is not self.head:
                self.delete(lru.key)

        new_node = Node(key, value)
        self.buckets[idx].append((key, new_node))
        self._add_to_front(new_node)
        self.size += 1

    def delete(self, key: str) -> bool:
        idx = self._bucket_index(key)
        bucket = self.buckets[idx]
        for i, (k, node) in enumerate(bucket):
            if k == key:
                bucket.pop(i)
                self._remove_node(node)
                self.size -= 1
                return True
        return False

    def keys_most_recent_first(self) -> list[str]:
        res: list[str] = []
        curr = self.head.next
        while curr is not None and curr is not self.tail:
            res.append(curr.key)
            curr = curr.next
        return res


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def parse_args(argv: list[str]) -> tuple[str, int, float]:
    catalog_path: Optional[str] = None
    size = 1000
    delay = 0.0

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--size":
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --size")
            raw_size = argv[i + 1]
            try:
                if "." in raw_size or not raw_size.strip():
                    raise ValueError
                size = int(raw_size)
            except ValueError:
                raise SystemExit(f"Ошибка: некорректный размер кэша '{raw_size}'")
            if size <= 0:
                raise SystemExit(f"Ошибка: размер кэша должен быть больше 0, получено '{raw_size}'")
            i += 2
        elif arg == "--delay":
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --delay")
            raw_delay = argv[i + 1]
            try:
                delay = float(raw_delay)
            except ValueError:
                raise SystemExit(f"Ошибка: некорректная задержка '{raw_delay}'")
            if math.isnan(delay) or math.isinf(delay) or delay < 0:
                raise SystemExit(f"Ошибка: задержка должна быть >= 0, получено '{raw_delay}'")
            i += 2
        elif arg.startswith("-"):
            raise SystemExit(f"Ошибка: неизвестный параметр '{arg}'")
        else:
            if catalog_path is not None:
                raise SystemExit(f"Ошибка: лишний аргумент '{arg}'")
            catalog_path = arg
            i += 1

    if catalog_path is None:
        raise SystemExit("Ошибка: не указан файл каталога")

    return catalog_path, size, delay


def load_catalog(path: str) -> ChainingMap:
    catalog = ChainingMap(1024)
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"Ошибка: не удалось открыть каталог '{path}': {e}", file=sys.stderr)
        sys.exit(1)

    for line_no, raw_line in enumerate(lines, 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ";" not in raw_line:
            print(f"Ошибка: строка {line_no}: нет разделителя ';'", file=sys.stderr)
            sys.exit(1)
        key_part, val_part = raw_line.split(";", 1)
        key = key_part.strip()
        val = val_part.strip()
        if not key or not val:
            print(f"Ошибка: строка {line_no}: пустой артикул или название товара", file=sys.stderr)
            sys.exit(1)
        if catalog.contains(key):
            print(f"Ошибка: строка {line_no}: дублирующийся артикул '{key}'", file=sys.stderr)
            sys.exit(1)
        catalog.set(key, val)

    return catalog


def process_commands(catalog: ChainingMap, capacity: int, delay: float) -> None:
    cache = ChainingLRUCache(capacity)
    out: list[str] = []

    text = sys.stdin.read()
    if text.startswith("\ufeff"):
        text = text[1:]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line == "list":
            keys = cache.keys_most_recent_first()
            cap_str = fmt_int(capacity)
            cnt_str = fmt_int(len(keys))
            if not keys:
                out.append(f"Список (0 из {cap_str}): пусто")
            else:
                out.append(f"Список ({cnt_str} из {cap_str}): {', '.join(keys)}")

        elif line.startswith("get") and (len(line) == 3 or line[3].isspace()):
            key = line[3:].strip()
            if not key:
                out.append("ОШИБКА: не указан артикул в команде get")
                continue
            cached_val = cache.get(key)
            if cached_val is not None:
                out.append(f'{key}: "{cached_val}"')
            else:
                if delay > 0:
                    time.sleep(delay)
                val = catalog.get(key)
                if val is not None:
                    cache.put(key, val)
                    out.append(f'{key}: "{val}"')
                else:
                    out.append(f"{key}: [товар не найден]")

        elif line.startswith("put") and (len(line) == 3 or line[3].isspace()):
            rest = line[3:].strip()
            if ";" not in rest:
                out.append("ОШИБКА: в команде put отсутствует ';'")
                continue
            key_part, val_part = rest.split(";", 1)
            key = key_part.strip()
            val = val_part.strip()
            if not key or not val:
                out.append("ОШИБКА: пустой артикул или товар в команде put")
                continue
            if ";" in key:
                out.append("ОШИБКА: недопустимый символ ';' в артикуле")
                continue
            cache.put(key, val)
            out.append(f"{key}: сохранено")

        elif line.startswith("del") and (len(line) == 3 or line[3].isspace()):
            key = line[3:].strip()
            if not key:
                out.append("ОШИБКА: не указан артикул в команде del")
                continue
            if cache.delete(key):
                out.append(f"{key}: удалено")
            else:
                out.append(f"{key}: нет в кэше")

        else:
            out.append(f"ОШИБКА: неизвестная или некорректная команда '{line}'")

    if out:
        sys.stdout.write("\n".join(out) + "\n")


def main() -> int:
    try:
        catalog_path, capacity, delay = parse_args(sys.argv[1:])
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2

    catalog = load_catalog(catalog_path)
    process_commands(catalog, capacity, delay)
    return 0


if __name__ == "__main__":
    sys.exit(main())