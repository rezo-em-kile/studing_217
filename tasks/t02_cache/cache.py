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
