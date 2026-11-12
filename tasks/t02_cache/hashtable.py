"""Хэш-таблица «ключ - значение» без встроенных словарей: метод цепочек.

Массив корзин; в каждой корзине - список пар [ключ, значение] с одинаковым номером
корзины (hash(ключ) по модулю числа корзин). Когда записей становится больше, чем корзин,
массив удваивается и все пары раскладываются заново, так что средняя длина цепочки
остаётся не больше 1 и поиск - в среднем O(1).
"""

INITIAL_BUCKETS = 8


class HashTable:
    def __init__(self):
        self.buckets = [[] for _ in range(INITIAL_BUCKETS)]
        self.count = 0

    def __len__(self):
        return self.count

    def _bucket(self, key):
        return self.buckets[hash(key) % len(self.buckets)]

    def get(self, key):
        """Значение по ключу или None."""
        for pair in self._bucket(key):
            if pair[0] == key:
                return pair[1]
        return None

    def insert(self, key, value):
        """Добавляет пару или заменяет значение существующего ключа."""
        bucket = self._bucket(key)
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value
                return
        bucket.append([key, value])
        self.count += 1
        if self.count > len(self.buckets):
            self._resize(len(self.buckets) * 2)

    def remove(self, key):
        """Удаляет ключ; возвращает True, если он был."""
        bucket = self._bucket(key)
        for index in range(len(bucket)):
            if bucket[index][0] == key:
                bucket[index] = bucket[-1]
                bucket.pop()
                self.count -= 1
                return True
        return False

    def _resize(self, size):
        old = self.buckets
        self.buckets = [[] for _ in range(size)]
        for bucket in old:
            for pair in bucket:
                self.buckets[hash(pair[0]) % size].append(pair)
