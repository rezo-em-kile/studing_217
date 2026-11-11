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


_DELETED = object()


class OpenAddressingMap:
    """Хэш-таблица каталога с открытой адресацией (линейное пробирование)."""

    def __init__(self, initial_cap: int = 1024):
        self.cap = initial_cap
        self.count = 0
        self.keys: list[object] = [None] * self.cap
        self.vals: list[Optional[str]] = [None] * self.cap

    def _grow(self) -> None:
        old_k = self.keys
        old_v = self.vals
        self.cap *= 2
        self.keys = [None] * self.cap
        self.vals = [None] * self.cap
        self.count = 0
        for k, v in zip(old_k, old_v):
            if k is not None and k is not _DELETED:
                self.put(str(k), str(v))

    def put(self, key: str, value: str) -> None:
        if (self.count + 1) * 2 >= self.cap:
            self._grow()
        mask = self.cap - 1
        idx = hash(key) & mask
        first_del = -1
        while True:
            cur = self.keys[idx]
            if cur is None:
                if first_del != -1:
                    idx = first_del
                self.keys[idx] = key
                self.vals[idx] = value
                self.count += 1
                return
            if cur is _DELETED:
                if first_del == -1:
                    first_del = idx
            elif cur == key:
                self.vals[idx] = value
                return
            idx = (idx + 1) & mask

    def get(self, key: str) -> Optional[str]:
        mask = self.cap - 1
        idx = hash(key) & mask
        while True:
            cur = self.keys[idx]
            if cur is None:
                return None
            if cur == key:
                return self.vals[idx]
            idx = (idx + 1) & mask

    def contains(self, key: str) -> bool:
        return self.get(key) is not None


class OpenAddressingLRUCache:
    """LRU-кэш на открытой адресации с периодической очисткой надгробий."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.size = 0
        self.cap = max(32, 1 << (capacity * 2).bit_length())
        self.keys: list[object] = [None] * self.cap
        self.nodes: list[Optional[Node]] = [None] * self.cap
        self.tombstones = 0

        self.head = Node("", "")
        self.tail = Node("", "")
        self.head.next = self.tail
        self.tail.prev = self.head

    def _rehash(self) -> None:
        old_nodes = [node for node in self.nodes if node is not None]
        self.keys = [None] * self.cap
        self.nodes = [None] * self.cap
        self.tombstones = 0
        mask = self.cap - 1
        for node in old_nodes:
            idx = hash(node.key) & mask
            while self.keys[idx] is not None:
                idx = (idx + 1) & mask
            self.keys[idx] = node.key
            self.nodes[idx] = node

    def _remove_node(self, node: Node) -> None:
        p = node.prev
        n = node.next
        if p is not None and n is not None:
            p.next = n
            n.prev = p

    def _add_front(self, node: Node) -> None:
        nxt = self.head.next
        node.prev = self.head
        node.next = nxt
        self.head.next = node
        if nxt is not None:
            nxt.prev = node

    def get(self, key: str) -> Optional[str]:
        mask = self.cap - 1
        idx = hash(key) & mask
        while True:
            cur = self.keys[idx]
            if cur is None:
                return None
            if cur == key:
                node = self.nodes[idx]
                if node is not None:
                    self._remove_node(node)
                    self._add_front(node)
                    return node.value
                return None
            idx = (idx + 1) & mask

    def put(self, key: str, value: str) -> None:
        if self.tombstones > (self.cap >> 2):
            self._rehash()

        mask = self.cap - 1
        idx = hash(key) & mask
        first_del = -1
        while True:
            cur = self.keys[idx]
            if cur is None:
                break
            if cur is _DELETED:
                if first_del == -1:
                    first_del = idx
            elif cur == key:
                node = self.nodes[idx]
                if node is not None:
                    node.value = value
                    self._remove_node(node)
                    self._add_front(node)
                return
            idx = (idx + 1) & mask

        if self.size >= self.capacity:
            lru = self.tail.prev
            if lru is not None and lru is not self.head:
                self.delete(lru.key)

        idx = hash(key) & mask
        first_del = -1
        while True:
            cur = self.keys[idx]
            if cur is None:
                if first_del != -1:
                    idx = first_del
                break
            if cur is _DELETED and first_del == -1:
                first_del = idx
            idx = (idx + 1) & mask

        node = Node(key, value)
        self.keys[idx] = key
        self.nodes[idx] = node
        self._add_front(node)
        self.size += 1

    def delete(self, key: str) -> bool:
        mask = self.cap - 1
        idx = hash(key) & mask
        while True:
            cur = self.keys[idx]
            if cur is None:
                return False
            if cur == key:
                node = self.nodes[idx]
                if node is not None:
                    self._remove_node(node)
                self.keys[idx] = _DELETED
                self.nodes[idx] = None
                self.size -= 1
                self.tombstones += 1
                return True
            idx = (idx + 1) & mask

    def keys_most_recent_first(self) -> list[str]:
        res: list[str] = []
        cur = self.head.next
        while cur is not None and cur is not self.tail:
            res.append(cur.key)
            cur = cur.next
        return res


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def parse_args(argv: list[str]) -> tuple[str, int, float]:
    cat_path: Optional[str] = None
    size = 1000
    delay = 0.0

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--size":
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --size")
            raw = argv[i + 1]
            try:
                if "." in raw or not raw.strip():
                    raise ValueError
                size = int(raw)
            except ValueError:
                raise SystemExit(f"Ошибка: некорректный размер кэша '{raw}'")
            if size <= 0:
                raise SystemExit(f"Ошибка: размер кэша должен быть больше 0, получено '{raw}'")
            i += 2
        elif arg == "--delay":
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --delay")
            raw = argv[i + 1]
            try:
                delay = float(raw)
            except ValueError:
                raise SystemExit(f"Ошибка: некорректная задержка '{raw}'")
            if math.isnan(delay) or math.isinf(delay) or delay < 0:
                raise SystemExit(f"Ошибка: задержка должна быть >= 0, получено '{raw}'")
            i += 2
        elif arg.startswith("-"):
            raise SystemExit(f"Ошибка: неизвестный параметр '{arg}'")
        else:
            if cat_path is not None:
                raise SystemExit(f"Ошибка: лишний аргумент '{arg}'")
            cat_path = arg
            i += 1

    if cat_path is None:
        raise SystemExit("Ошибка: не указан файл каталога")

    return cat_path, size, delay


def load_catalog(path: str) -> OpenAddressingMap:
    catalog = OpenAddressingMap(1024)
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"Ошибка: не удалось открыть каталог '{path}': {e}", file=sys.stderr)
        sys.exit(1)

    for line_no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ";" not in raw:
            print(f"Ошибка: строка {line_no}: нет разделителя ';'", file=sys.stderr)
            sys.exit(1)
        k_part, v_part = raw.split(";", 1)
        k = k_part.strip()
        v = v_part.strip()
        if not k or not v:
            print(f"Ошибка: строка {line_no}: пустой артикул или название товара", file=sys.stderr)
            sys.exit(1)
        if catalog.contains(k):
            print(f"Ошибка: строка {line_no}: дублирующийся артикул '{k}'", file=sys.stderr)
            sys.exit(1)
        catalog.put(k, v)

    return catalog


def process_commands(catalog: OpenAddressingMap, capacity: int, delay: float) -> None:
    cache = OpenAddressingLRUCache(capacity)
    out: list[str] = []

    text = sys.stdin.read()
    if text.startswith("\ufeff"):
        text = text[1:]

    for raw in text.splitlines():
        line = raw.strip()
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
            k = line[3:].strip()
            if not k:
                out.append("ОШИБКА: не указан артикул в команде get")
                continue
            v = cache.get(k)
            if v is not None:
                out.append(f'{k}: "{v}"')
            else:
                if delay > 0:
                    time.sleep(delay)
                val = catalog.get(k)
                if val is not None:
                    cache.put(k, val)
                    out.append(f'{k}: "{val}"')
                else:
                    out.append(f"{k}: [товар не найден]")

        elif line.startswith("put") and (len(line) == 3 or line[3].isspace()):
            rest = line[3:].strip()
            if ";" not in rest:
                out.append("ОШИБКА: в команде put отсутствует ';'")
                continue
            k_part, v_part = rest.split(";", 1)
            k = k_part.strip()
            v = v_part.strip()
            if not k or not v:
                out.append("ОШИБКА: пустой артикул или товар в команде put")
                continue
            if ";" in k:
                out.append("ОШИБКА: недопустимый символ ';' в артикуле")
                continue
            cache.put(k, v)
            out.append(f"{k}: сохранено")

        elif line.startswith("del") and (len(line) == 3 or line[3].isspace()):
            k = line[3:].strip()
            if not k:
                out.append("ОШИБКА: не указан артикул в команде del")
                continue
            if cache.delete(k):
                out.append(f"{k}: удалено")
            else:
                out.append(f"{k}: нет в кэше")

        else:
            out.append(f"ОШИБКА: неизвестная или некорректная команда '{line}'")

    if out:
        sys.stdout.write("\n".join(out) + "\n")


def main() -> int:
    try:
        cat_path, capacity, delay = parse_args(sys.argv[1:])
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2

    catalog = load_catalog(cat_path)
    process_commands(catalog, capacity, delay)
    return 0


if __name__ == "__main__":
    sys.exit(main())