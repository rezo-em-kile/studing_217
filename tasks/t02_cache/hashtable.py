"""Таблица «ключ - значение» без встроенных словарей.

Базовая версия: список пар и последовательный поиск. Работает правильно, но каждый
поиск - O(n). Быстрые варианты (цепочки и открытая адресация) проверяются в ветках
экспериментов.
"""


class HashTable:
    def __init__(self):
        self.keys = []
        self.values = []

    def __len__(self):
        return len(self.keys)

    def _find(self, key):
        for index in range(len(self.keys)):
            if self.keys[index] == key:
                return index
        return -1

    def get(self, key):
        """Значение по ключу или None."""
        index = self._find(key)
        return None if index < 0 else self.values[index]

    def insert(self, key, value):
        """Добавляет пару или заменяет значение существующего ключа."""
        index = self._find(key)
        if index < 0:
            self.keys.append(key)
            self.values.append(value)
        else:
            self.values[index] = value

    def remove(self, key):
        """Удаляет ключ; возвращает True, если он был."""
        index = self._find(key)
        if index < 0:
            return False
        last = len(self.keys) - 1
        self.keys[index] = self.keys[last]
        self.values[index] = self.values[last]
        self.keys.pop()
        self.values.pop()
        return True
