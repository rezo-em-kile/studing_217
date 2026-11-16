"""Сводка оценок класса.

В каждой строке ведомости - ученик и его оценки: «Иванов Иван: 5 4 4 3».
Программа считает средний балл и медиану каждого ученика, распределение оценок
и находит лучших учеников.

    python grades.py samples/class.txt
"""
from __future__ import annotations

import sys

MARKS = (2, 3, 4, 5)


class GradesError(ValueError):
    """Ошибка в строке ведомости."""


def parse_line(line):
    """Строка ведомости → (имя, список оценок); ошибка - GradesError."""
    name, sep, rest = line.partition(":")
    name = " ".join(name.split())
    if not sep or not name:
        raise GradesError(f"нет имени ученика: {line.strip()!r}")
    marks = []
    for item in rest.split():
        if not item.isdigit() or int(item) not in MARKS:
            raise GradesError(f"{name}: неверная оценка {item!r}")
        marks.append(int(item))
    if not marks:
        raise GradesError(f"{name}: нет оценок")
    return name, marks


def read_records(lines):
    """Разобрать ведомость; пустые строки пропускаются."""
    return [parse_line(line) for line in lines if line.strip()]


def average(marks):
    """Средний балл, округлённый до сотых."""
    return round(sum(marks) / len(marks), 2)


def median(marks):
    ordered = sorted(marks)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def distribution(records):
    counts = {mark: 0 for mark in MARKS}
    for _, marks in records:
        for mark in marks:
            counts[mark] += 1
    return counts


def best_students(records):
    if not records:
        return []
    best = max(average(marks) for _, marks in records)
    return sorted(name for name, marks in records if average(marks) == best)


def format_summary(records):
    lines = [f"{name}: средний балл {average(marks):.2f}, медиана {median(marks):g}"
             for name, marks in records]
    counts = distribution(records)
    lines.append("Распределение оценок: " + ", ".join(f"«{m}» - {counts[m]}" for m in MARKS))
    lines.append("Лучшие ученики: " + (", ".join(best_students(records)) or "-"))
    return "\n".join(lines)


def main(argv=None):
    """Точка входа командной строки."""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Запуск: python grades.py ведомость.txt", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as file:
            records = read_records(file)
    except (OSError, GradesError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    print(format_summary(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
