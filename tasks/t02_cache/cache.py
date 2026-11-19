import sys
import time

_DELETED = object()


class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class OpenAddressingHashTable:
    def __init__(self, capacity=16):
        self.capacity = capacity
        self.keys = [None] * capacity
        self.values = [None] * capacity
        self.count = 0
        self.used = 0

    def _resize(self):
        old_keys = self.keys
        old_values = self.values
        self.capacity *= 2
        self.keys = [None] * self.capacity
        self.values = [None] * self.capacity
        self.count = 0
        self.used = 0
        for k, v in zip(old_keys, old_values):
            if k is not None and k is not _DELETED:
                self.put(k, v)

    def get(self, key):
        mask = self.capacity - 1
        idx = hash(key) & mask
        while True:
            cur_k = self.keys[idx]
            if cur_k is None:
                return None
            if cur_k is not _DELETED and cur_k == key:
                return self.values[idx]
            idx = (idx + 1) & mask

    def put(self, key, val):
        if (self.used + 1) * 2 >= self.capacity:
            self._resize()

        mask = self.capacity - 1
        idx = hash(key) & mask
        first_deleted = -1

        while True:
            cur_k = self.keys[idx]
            if cur_k is None:
                target = first_deleted if first_deleted != -1 else idx
                if first_deleted == -1:
                    self.used += 1
                self.keys[target] = key
                self.values[target] = val
                self.count += 1
                return
            if cur_k is _DELETED:
                if first_deleted == -1:
                    first_deleted = idx
            elif cur_k == key:
                self.values[idx] = val
                return
            idx = (idx + 1) & mask

    def remove(self, key):
        mask = self.capacity - 1
        idx = hash(key) & mask
        while True:
            cur_k = self.keys[idx]
            if cur_k is None:
                return False
            if cur_k is not _DELETED and cur_k == key:
                self.keys[idx] = _DELETED
                self.values[idx] = None
                self.count -= 1
                return True
            idx = (idx + 1) & mask


class LRUCache:
    def __init__(self, max_size):
        self.max_size = max_size
        self.table = OpenAddressingHashTable()
        self.head = Node(None, None)
        self.tail = Node(None, None)
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_front(self, node):
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove_node(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _move_to_front(self, node):
        self._remove_node(node)
        self._add_front(node)

    def get(self, key):
        node = self.table.get(key)
        if node is None:
            return None
        self._move_to_front(node)
        return node.value

    def put(self, key, value):
        node = self.table.get(key)
        if node is not None:
            node.value = value
            self._move_to_front(node)
            return

        if self.table.count >= self.max_size:
            lru = self.tail.prev
            if lru is not self.head:
                self._remove_node(lru)
                self.table.remove(lru.key)

        new_node = Node(key, value)
        self._add_front(new_node)
        self.table.put(key, new_node)

    def delete(self, key):
        node = self.table.get(key)
        if node is None:
            return False
        self._remove_node(node)
        self.table.remove(key)
        return True

    def keys_recent_first(self):
        res = []
        curr = self.head.next
        while curr is not self.tail:
            res.append(curr.key)
            curr = curr.next
        return res


def format_num(n):
    return f"{n:,}".replace(",", " ")


def fail_init(msg, code=1):
    print(f"Ошибка: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_args(argv):
    catalog_path = None
    size = 1000
    delay = 0.0
    size_seen = False
    delay_seen = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--size":
            if size_seen or i + 1 >= len(argv):
                fail_init("некорректный параметр --size", code=2)
            try:
                size = int(argv[i + 1])
            except ValueError:
                fail_init("параметр --size должен быть целым числом", code=2)
            if size <= 0:
                fail_init("параметр --size должен быть больше 0", code=2)
            size_seen = True
            i += 2
        elif arg.startswith("--size="):
            if size_seen:
                fail_init("дублирующийся параметр --size", code=2)
            _, size_str = arg.split("=", 1)
            try:
                size = int(size_str)
            except ValueError:
                fail_init("параметр --size должен быть целым числом", code=2)
            if size <= 0:
                fail_init("параметр --size должен быть больше 0", code=2)
            size_seen = True
            i += 1
        elif arg == "--delay":
            if delay_seen or i + 1 >= len(argv):
                fail_init("некорректный параметр --delay", code=2)
            try:
                delay = float(argv[i + 1])
            except ValueError:
                fail_init("параметр --delay должен быть числом", code=2)
            if delay < 0 or delay != delay:
                fail_init("параметр --delay должен быть >= 0", code=2)
            delay_seen = True
            i += 2
        elif arg.startswith("--delay="):
            if delay_seen:
                fail_init("дублирующийся параметр --delay", code=2)
            _, delay_str = arg.split("=", 1)
            try:
                delay = float(delay_str)
            except ValueError:
                fail_init("параметр --delay должен быть числом", code=2)
            if delay < 0 or delay != delay:
                fail_init("параметр --delay должен быть >= 0", code=2)
            delay_seen = True
            i += 1
        elif arg.startswith("-"):
            fail_init(f"неизвестный параметр '{arg}'", code=2)
        else:
            if catalog_path is not None:
                fail_init("указано более одного файла каталога", code=2)
            catalog_path = arg
            i += 1

    if catalog_path is None:
        fail_init("не указан файл каталога", code=2)

    return catalog_path, size, delay


def load_catalog(path):
    catalog = OpenAddressingHashTable()
    try:
        with open(path, encoding="utf-8") as f:
            for line_num, raw_line in enumerate(f, start=1):
                line = raw_line.rstrip("\r\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if ";" not in line:
                    fail_init(f"строка {line_num}: отсутствует разделитель ';'", code=1)
                sku, title = line.split(";", 1)
                sku = sku.strip()
                title = title.strip()
                if not sku:
                    fail_init(f"строка {line_num}: пустой артикул", code=1)
                if not title:
                    fail_init(f"строка {line_num}: пустое название товара для артикула '{sku}'", code=1)
                catalog.put(sku, title)
    except OSError:
        fail_init(f"не удалось открыть файл каталога '{path}'", code=1)
    except UnicodeDecodeError:
        fail_init(f"файл каталога '{path}' должен быть в кодировке UTF-8", code=1)

    return catalog


def main():
    _, *cli_args = sys.argv
    catalog_path, max_size, delay = parse_args(cli_args)
    catalog = load_catalog(catalog_path)
    cache = LRUCache(max_size)

    try:
        lines = sys.stdin.read().splitlines()
    except UnicodeDecodeError:
        fail_init("входные команды должны быть в кодировке UTF-8", code=1)

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        cmd, *rest = line.split(None, 1)
        arg = rest.pop().strip() if rest else ""

        if cmd == "get":
            if not arg:
                print("ОШИБКА: не указан артикул для команды get")
                continue
            val = cache.get(arg)
            if val is not None:
                print(f'{arg}: "{val}"')
            else:
                if delay > 0:
                    time.sleep(delay)
                catalog_val = catalog.get(arg)
                if catalog_val is not None:
                    cache.put(arg, catalog_val)
                    print(f'{arg}: "{catalog_val}"')
                else:
                    print(f"{arg}: [товар не найден]")

        elif cmd == "put":
            if not arg or ";" not in arg:
                print("ОШИБКА: неверный формат команды put (ожидается 'put артикул; товар')")
                continue
            sku, title = arg.split(";", 1)
            sku = sku.strip()
            title = title.strip()
            if not sku:
                print("ОШИБКА: пустой артикул в команде put")
                continue
            if not title:
                print("ОШИБКА: пустое название товара в команде put")
                continue
            cache.put(sku, title)
            print(f"{sku}: сохранено")

        elif cmd == "del":
            if not arg:
                print("ОШИБКА: не указан артикул для команды del")
                continue
            if cache.delete(arg):
                print(f"{arg}: удалено")
            else:
                print(f"{arg}: отсутствует в кэше")

        elif cmd == "list":
            if arg:
                print("ОШИБКА: команда list не принимает аргументов")
                continue
            keys = cache.keys_recent_first()
            cur_fmt = format_num(len(keys))
            max_fmt = format_num(max_size)
            if keys:
                print(f"Список ({cur_fmt} из {max_fmt}): {', '.join(keys)}")
            else:
                print(f"Список (0 из {max_fmt}): пусто")

        else:
            print(f"ОШИБКА: неизвестная команда '{cmd}'")


if __name__ == "__main__":
    main()
