"""Симулятор очереди в магазине.

Режим 1 (покупатели из стандартного ввода):
    python queue_sim.py [--cashiers N] [--max-queue N|none] [--close T] < customers.txt
Режим 2 (случайный поток):
    python queue_sim.py [--cashiers N] [--max-queue N|none] --seed S [--minutes M] [--interval I] [--service МИН-МАКС]
"""
import heapq
import math
import random
import re
import sys
from collections import deque

NUMBER_RE = re.compile(r"^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")
INTEGER_RE = re.compile(r"^[0-9]+$")
OPTIONS = ("--cashiers", "--max-queue", "--close", "--seed", "--minutes", "--interval", "--service")
RANDOM_ONLY = ("--minutes", "--interval", "--service")


class UsageError(Exception):
    """Неверные аргументы командной строки (код 2)."""


class DataError(Exception):
    """Ошибка во входных данных (код 1)."""


def parse_number(text):
    """Конечное число из строки или None («nan», «inf», «1,5» - не числа)."""
    if not NUMBER_RE.match(text):
        return None
    value = float(text)
    return value if math.isfinite(value) else None


def parse_args(args):
    values = {}
    position = 0
    while position < len(args):
        arg = args[position]
        if arg not in OPTIONS:
            raise UsageError(f"неизвестный аргумент «{arg}»")
        if arg in values:
            raise UsageError(f"параметр {arg} указан дважды")
        if position + 1 >= len(args):
            raise UsageError(f"после {arg} нужно значение")
        values[arg] = args[position + 1]
        position += 2

    options = {"cashiers": 3, "max_queue": 10, "close": None, "seed": None,
               "minutes": 720.0, "interval": 0.5, "service": (2.0, 5.0)}
    if "--cashiers" in values:
        text = values["--cashiers"]
        if not INTEGER_RE.match(text):
            raise UsageError(f"--cashiers: нужно целое число ≥ 0, получено «{text}»")
        options["cashiers"] = int(text)
    if "--max-queue" in values:
        text = values["--max-queue"]
        if text == "none":
            options["max_queue"] = None
        elif INTEGER_RE.match(text):
            options["max_queue"] = int(text)
        else:
            raise UsageError(f"--max-queue: нужно целое число ≥ 0 или none, получено «{text}»")
    if "--seed" in values:
        text = values["--seed"]
        if not re.match(r"^-?[0-9]+$", text):
            raise UsageError(f"--seed: нужно целое число, получено «{text}»")
        options["seed"] = int(text)
        if "--close" in values:
            raise UsageError("--close задаётся только для покупателей из стандартного ввода; "
                             "в случайном режиме время закрытия - --minutes")
    else:
        extra = [name for name in RANDOM_ONLY if name in values]
        if extra:
            raise UsageError(f"{', '.join(extra)} - только для случайного режима (нужен --seed)")
    if "--close" in values:
        close = parse_number(values["--close"])
        if close is None or close < 0:
            raise UsageError(f"--close: нужно число минут ≥ 0, получено «{values['--close']}»")
        options["close"] = close
    if "--minutes" in values:
        minutes = parse_number(values["--minutes"])
        if minutes is None or minutes < 0:
            raise UsageError(f"--minutes: нужно число минут ≥ 0, получено «{values['--minutes']}»")
        options["minutes"] = minutes
    if "--interval" in values:
        interval = parse_number(values["--interval"])
        if interval is None or interval <= 0:
            raise UsageError(f"--interval: нужно число минут > 0, получено «{values['--interval']}»")
        options["interval"] = interval
    if "--service" in values:
        text = values["--service"]
        low_text, dash, high_text = text.partition("-")
        low, high = parse_number(low_text), parse_number(high_text)
        if not dash or low is None or high is None or low <= 0 or high < low:
            raise UsageError(f"--service: нужно МИН-МАКС, 0 < МИН ≤ МАКС, получено «{text}»")
        options["service"] = (low, high)
    return options


def read_customers(text):
    customers = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise DataError(f"строка {number}: нужно два числа «приход обслуживание», получено «{line}»")
        arrival, service = parse_number(parts[0]), parse_number(parts[1])
        if arrival is None or arrival < 0:
            raise DataError(f"строка {number}: неверное время прихода «{parts[0]}»")
        if service is None or service <= 0:
            raise DataError(f"строка {number}: время обслуживания должно быть больше 0, получено «{parts[1]}»")
        customers.append((arrival, service))
    return customers


def generate_customers(seed, minutes, interval, service):
    """Пуассоновский поток: интервалы между приходами экспоненциальные со средним interval."""
    rng = random.Random(seed)
    low, high = service
    customers = []
    moment = 0.0
    while True:
        moment += rng.expovariate(1 / interval)
        if moment >= minutes:
            return customers
        customers.append((moment, rng.uniform(low, high)))


def simulate(customers, cashiers, max_queue, close):
    """Моделирует работу магазина и возвращает статистику."""
    order = sorted(range(len(customers)), key=lambda i: customers[i][0])
    free = list(range(cashiers))
    busy = []
    queue = deque()
    served_by = [0] * cashiers
    busy_time = [0.0] * cashiers
    stats = {"arrived": 0, "served": 0, "balked": 0, "waits": [], "service": 0.0, "max_queue": 0, "end": 0.0}

    def start(cashier, moment, arrival, service):
        served_by[cashier] += 1
        busy_time[cashier] += service
        stats["served"] += 1
        stats["service"] += service
        stats["waits"].append(moment - arrival)
        finish = moment + service
        stats["end"] = max(stats["end"], finish)
        heapq.heappush(busy, (finish, cashier))

    def release_until(moment):
        while busy and busy[0][0] <= moment:
            finish, cashier = heapq.heappop(busy)
            if queue:
                arrival, service = queue.popleft()
                start(cashier, finish, arrival, service)
            else:
                heapq.heappush(free, cashier)

    for index in order:
        arrival, service = customers[index]
        if close is not None and arrival >= close:
            break
        release_until(arrival)
        stats["arrived"] += 1
        if free:
            start(heapq.heappop(free), arrival, arrival, service)
        elif cashiers > 0 and (max_queue is None or len(queue) < max_queue):
            queue.append((arrival, service))
            stats["max_queue"] = max(stats["max_queue"], len(queue))
        else:
            stats["balked"] += 1
    release_until(math.inf)

    duration = stats["end"] if close is None else close
    stats["cashiers"] = [(served_by[i], busy_time[i] / duration if duration > 0 else 0.0)
                         for i in range(cashiers)]
    return stats


def group(text):
    """Пробел между разрядами: 1442 -> «1 442», 1234.5 -> «1 234.5»."""
    return text.replace(",", " ")


def count_text(count):
    return group(f"{count:,}")


def plural(count, one, few, many):
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def minutes_text(value):
    return group(f"{value:,.1f}")


def build_report(stats, seed=None):
    waits = stats["waits"]
    average_wait = sum(waits) / len(waits) if waits else 0.0
    average_service = stats["service"] / stats["served"] if stats["served"] else 0.0
    queue = stats["max_queue"]
    title = "Результаты симуляции:" if seed is None else f"Результаты симуляции (семя: {seed}):"
    lines = [
        title,
        "",
        "Общая статистика:",
        f"  Всего пришло покупателей: {count_text(stats['arrived'])}",
        f"  Обслужено покупателей: {count_text(stats['served'])}",
        f"  Ушло из-за длинной очереди: {count_text(stats['balked'])}",
        "",
        "Время ожидания:",
        f"  Среднее время ожидания: {minutes_text(average_wait)} мин",
        f"  Максимальное время ожидания: {minutes_text(max(waits) if waits else 0.0)} мин",
        f"  Минимальное время ожидания: {minutes_text(min(waits) if waits else 0.0)} мин",
        "",
        "Очередь:",
        f"  Максимальная длина очереди: {count_text(queue)} {plural(queue, 'человек', 'человека', 'человек')}",
        f"  Среднее время обслуживания: {minutes_text(average_service)} мин на покупателя",
        "",
        "Загрузка кассиров:",
    ]
    if not stats["cashiers"]:
        lines.append("  кассиров нет")
    for number, (served, load) in enumerate(stats["cashiers"], 1):
        word = plural(served, "покупателя", "покупателей", "покупателей")
        lines.append(f"  Кассир {number}: обслужил {count_text(served)} {word}, загрузка {load * 100:.0f}%")
    return lines


def format_trace(events):
    """ЧЕРНОВИК: журнал событий симуляции для отладки (--trace). Пока не подключён к main.

    events - список (время, кассир, что произошло). TODO: собирать события в simulate,
    не замедлив её на сотнях тысяч покупателей.
    """
    lines = []
    for moment, cashier, what in events:
        who = "очередь" if cashier is None else f"касса {cashier + 1}"
        lines.append(f"{moment:8.2f}  {who:<10} {what}")
    return lines


def use_utf8_streams():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main():
    use_utf8_streams()
    try:
        options = parse_args(sys.argv[1:])
    except UsageError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        sys.exit(2)
    if options["seed"] is not None:
        customers = generate_customers(options["seed"], options["minutes"], options["interval"],
                                       options["service"])
        close = options["minutes"]
    else:
        try:
            customers = read_customers(sys.stdin.read().lstrip("﻿"))
        except DataError as error:
            print(f"Ошибка: {error}", file=sys.stderr)
            sys.exit(1)
        close = options["close"]
    stats = simulate(customers, options["cashiers"], options["max_queue"], close)
    for line in build_report(stats, options["seed"]):
        print(line)


if __name__ == "__main__":
    main()
