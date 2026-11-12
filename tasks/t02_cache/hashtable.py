"""Хэш-таблица «ключ - значение» без встроенных словарей: открытая адресация.

Все пары лежат прямо в массиве ячеек. Ключ ищется, начиная с ячейки hash(ключ) по модулю
размера, и дальше подряд (линейное пробирование) до пустой ячейки. Удалённая ячейка
помечается «надгробием», чтобы не обрывать цепочку поиска для других ключей. Когда занятых
ячеек (вместе с надгробиями) становится больше половины, массив перестраивается.
"""

INITIAL_SLOTS = 8
EMPTY = None
DELETED = object()


class HashTable:
    def __init__(self):
        self.keys = [EMPTY] * INITIAL_SLOTS
        self.values = [EMPTY] * INITIAL_SLOTS
        self.count = 0
        self.used = 0

    def __len__(self):
        return self.count

    def _find(self, key):
        """Номер ячейки с ключом или -1."""
        keys = self.keys
        mask = len(keys) - 1
        index = hash(key) & mask
        while True:
            current = keys[index]
            if current is EMPTY:
                return -1
            if current is not DELETED and current == key:
                return index
            index = (index + 1) & mask

    def get(self, key):
        """Значение по ключу или None."""
        index = self._find(key)
        return None if index < 0 else self.values[index]

    def insert(self, key, value):
        """Добавляет пару или заменяет значение существующего ключа."""
        index = self._find(key)
        if index >= 0:
            self.values[index] = value
            return
        if (self.used + 1) * 2 > len(self.keys):
            self._rebuild()
        keys = self.keys
        mask = len(keys) - 1
        index = hash(key) & mask
        while keys[index] is not EMPTY and keys[index] is not DELETED:
            index = (index + 1) & mask
        if keys[index] is EMPTY:
            self.used += 1
        keys[index] = key
        self.values[index] = value
        self.count += 1

    def remove(self, key):
        """Удаляет ключ; возвращает True, если он был."""
        index = self._find(key)
        if index < 0:
            return False
        self.keys[index] = DELETED
        self.values[index] = EMPTY
        self.count -= 1
        return True

    def _rebuild(self):
        """Новый массив (размер - степень двойки) без надгробий."""
        size = INITIAL_SLOTS
        while size < self.count * 4:
            size *= 2
        old_keys, old_values = self.keys, self.values
        self.keys = [EMPTY] * size
        self.values = [EMPTY] * size
        self.used = self.count
        mask = size - 1
        for position in range(len(old_keys)):
            key = old_keys[position]
            if key is EMPTY or key is DELETED:
                continue
            index = hash(key) & mask
            while self.keys[index] is not EMPTY:
                index = (index + 1) & mask
            self.keys[index] = key
            self.values[index] = old_values[position]
