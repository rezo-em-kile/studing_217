class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class ChainingHashTable:
    def __init__(self, capacity=16):
        self.capacity = capacity
        self.buckets = [[] for _ in range(capacity)]
        self.count = 0

    def _index(self, key):
        return hash(key) % self.capacity

    def _resize(self):
        old_buckets = self.buckets
        self.capacity *= 2
        self.buckets = [[] for _ in range(self.capacity)]
        for bucket in old_buckets:
            for key, val in bucket:
                idx = self._index(key)
                self.buckets[idx].append((key, val))

    def get(self, key):
        idx = self._index(key)
        for k, val in self.buckets[idx]:
            if k == key:
                return val
        return None

    def put(self, key, val):
        idx = self._index(key)
        bucket = self.buckets[idx]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, val)
                return
        bucket.append((key, val))
        self.count += 1
        if self.count > self.capacity * 0.75:
            self._resize()

    def remove(self, key):
        idx = self._index(key)
        bucket = self.buckets[idx]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket.pop(i)
                self.count -= 1
                return True
        return False


class LRUCache:
    def __init__(self, max_size):
        self.max_size = max_size
        self.table = ChainingHashTable()
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
