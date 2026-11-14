import heapq
import math
import random
import sys
from collections import deque
from typing import Optional


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def plural_person(n: int) -> str:
    rem100 = n % 100
    rem10 = n % 10
    if 11 <= rem100 <= 14:
        return "человек"
    if rem10 in (2, 3, 4):
        return "человека"
    return "человек"


def plural_customer(n: int) -> str:
    rem100 = n % 100
    rem10 = n % 10
    if 11 <= rem100 <= 14:
        return "покупателей"
    if rem10 == 1:
        return "покупателя"
    return "покупателей"


def parse_non_neg_float(raw: str, name: str) -> float:
    try:
        val = float(raw)
    except ValueError:
        raise SystemExit(f"Ошибка: некорректное число для {name}: '{raw}'")
    if math.isnan(val) or math.isinf(val) or val < 0:
        raise SystemExit(f"Ошибка: параметр {name} должен быть >= 0, получено '{raw}'")
    return val


def parse_pos_float(raw: str, name: str) -> float:
    val = parse_non_neg_float(raw, name)
    if val <= 0:
        raise SystemExit(f"Ошибка: параметр {name} должен быть > 0, получено '{raw}'")
    return val


def parse_non_neg_int(raw: str, name: str) -> int:
    if not raw or not raw.strip() or "." in raw:
        raise SystemExit(f"Ошибка: некорректное целое число для {name}: '{raw}'")
    try:
        val = int(raw)
    except ValueError:
        raise SystemExit(f"Ошибка: некорректное целое число для {name}: '{raw}'")
    if val < 0:
        raise SystemExit(f"Ошибка: параметр {name} должен быть >= 0, получено '{raw}'")
    return val


def parse_args(argv: list[str]) -> dict:
    seen: set[str] = set()

    def mark(opt: str) -> None:
        if opt in seen:
            raise SystemExit(f"Ошибка: повторный параметр '{opt}'")
        seen.add(opt)

    cashiers = 3
    max_queue: Optional[int] = 10
    close_time: Optional[float] = None
    seed: Optional[int] = None
    minutes: Optional[float] = None
    interval: Optional[float] = None
    service_range: Optional[tuple[float, float]] = None

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--cashiers":
            mark(arg)
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --cashiers")
            cashiers = parse_non_neg_int(argv[i + 1], "--cashiers")
            i += 2
        elif arg == "--max-queue":
            mark(arg)
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --max-queue")
            raw_q = argv[i + 1]
            if raw_q == "none":
                max_queue = None
            else:
                max_queue = parse_non_neg_int(raw_q, "--max-queue")
            i += 2
        elif arg == "--close":
            mark(arg)
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --close")
            close_time = parse_non_neg_float(argv[i + 1], "--close")
            i += 2
        elif arg == "--seed":
            mark(arg)
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --seed")
            raw_s = argv[i + 1]
            if not raw_s or not raw_s.strip() or "." in raw_s:
                raise SystemExit(f"Ошибка: некорректное семя '{raw_s}'")
            try:
                seed = int(raw_s)
            except ValueError:
                raise SystemExit(f"Ошибка: некорректное семя '{raw_s}'")
            i += 2
        elif arg == "--minutes":
            mark(arg)
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --minutes")
            minutes = parse_non_neg_float(argv[i + 1], "--minutes")
            i += 2
        elif arg == "--interval":
            mark(arg)
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --interval")
            interval = parse_pos_float(argv[i + 1], "--interval")
            i += 2
        elif arg == "--service":
            mark(arg)
            if i + 1 >= len(argv):
                raise SystemExit("Ошибка: не указано значение для --service")
            raw_srv = argv[i + 1]
            parts = raw_srv.split("-")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise SystemExit(f"Ошибка: некорректный диапазон обслуживания '{raw_srv}'")
            s_min = parse_pos_float(parts[0], "--service")
            s_max = parse_pos_float(parts[1], "--service")
            if s_max < s_min:
                raise SystemExit(f"Ошибка: некорректный диапазон обслуживания '{raw_srv}'")
            service_range = (s_min, s_max)
            i += 2
        else:
            raise SystemExit(f"Ошибка: неизвестный или лишний аргумент '{arg}'")

    if seed is not None:
        if close_time is not None:
            raise SystemExit("Ошибка: параметр --close нельзя использовать вместе с --seed")
        if minutes is None:
            minutes = 720.0
        if interval is None:
            interval = 0.5
        if service_range is None:
            service_range = (2.0, 5.0)
    else:
        if minutes is not None or interval is not None or service_range is not None:
            raise SystemExit("Ошибка: параметры --minutes, --interval и --service требуют --seed")

    return {
        "cashiers": cashiers,
        "max_queue": max_queue,
        "close_time": close_time,
        "seed": seed,
        "minutes": minutes,
        "interval": interval,
        "service_range": service_range,
    }


def read_customers_stdin() -> list[tuple[float, float]]:
    text = sys.stdin.read()
    if text.startswith("\ufeff"):
        text = text[1:]

    people: list[tuple[float, float]] = []
    for line_no, raw_line in enumerate(text.splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) != 2:
            print(f"Ошибка: строка {line_no}: ожидалось два числа (приход и обслуживание)", file=sys.stderr)
            sys.exit(1)
        try:
            arr = float(parts[0])
            srv = float(parts[1])
        except ValueError:
            print(f"Ошибка: строка {line_no}: некорректные числа '{stripped}'", file=sys.stderr)
            sys.exit(1)

        if math.isnan(arr) or math.isinf(arr) or arr < 0:
            print(f"Ошибка: строка {line_no}: некорректное время прихода '{parts[0]}'", file=sys.stderr)
            sys.exit(1)
        if math.isnan(srv) or math.isinf(srv) or srv <= 0:
            print(f"Ошибка: строка {line_no}: время обслуживания должно быть > 0, получено '{parts[1]}'", file=sys.stderr)
            sys.exit(1)

        people.append((arr, srv))

    return people


def generate_customers(seed: int, minutes: float, interval: float, srv_range: tuple[float, float]) -> list[tuple[float, float]]:
    rng = random.Random(seed)
    people: list[tuple[float, float]] = []
    t = 0.0
    s_min, s_max = srv_range
    rate = 1.0 / interval

    while True:
        t += rng.expovariate(rate)
        if t >= minutes:
            break
        srv = rng.uniform(s_min, s_max)
        people.append((t, srv))

    return people


def run_simulation(
    people: list[tuple[float, float]],
    num_cashiers: int,
    max_queue: Optional[int],
    close_time: Optional[float],
) -> dict:
    # Фильтруем пришедших после закрытия и сортируем с сохранением исходного порядка
    indexed = [(arr, idx, srv) for idx, (arr, srv) in enumerate(people) if close_time is None or arr < close_time]
    indexed.sort(key=lambda item: (item[0], item[1]))

    arrived = len(indexed)
    served = 0
    balked = 0
    total_wait = 0.0
    max_wait = 0.0
    min_wait: Optional[float] = None
    total_service = 0.0
    max_q_len = 0

    cashier_served = [0] * num_cashiers
    cashier_busy = [0.0] * num_cashiers
    last_finish = 0.0

    # Куча занятых касс: (время_освобождения, номер_кассы)
    busy_heap: list[tuple[float, int]] = []
    # Куча свободных касс: номер_кассы
    free_cashiers: list[int] = list(range(num_cashiers))
    heapq.heapify(free_cashiers)

    # Очередь ожидающих: (время_прихода, длительность_обслуживания)
    queue: deque[tuple[float, float]] = deque()

    def advance_to(target_time: float) -> None:
        nonlocal served, total_wait, max_wait, min_wait, total_service, last_finish
        while busy_heap and busy_heap[0][0] <= target_time:
            free_t, c_idx = heapq.heappop(busy_heap)
            if queue:
                q_arr, q_srv = queue.popleft()
                wait = free_t - q_arr
                if wait < 0:
                    wait = 0.0
                total_wait += wait
                if wait > max_wait:
                    max_wait = wait
                if min_wait is None or wait < min_wait:
                    min_wait = wait

                end_t = free_t + q_srv
                if end_t > last_finish:
                    last_finish = end_t
                served += 1
                total_service += q_srv
                cashier_served[c_idx] += 1
                cashier_busy[c_idx] += q_srv
                heapq.heappush(busy_heap, (end_t, c_idx))
            else:
                heapq.heappush(free_cashiers, c_idx)

    for arr, _, srv in indexed:
        advance_to(arr)

        if num_cashiers == 0:
            balked += 1
            continue

        if free_cashiers:
            c_idx = heapq.heappop(free_cashiers)
            if min_wait is None or 0.0 < min_wait:
                min_wait = 0.0
            end_t = arr + srv
            if end_t > last_finish:
                last_finish = end_t
            served += 1
            total_service += srv
            cashier_served[c_idx] += 1
            cashier_busy[c_idx] += srv
            heapq.heappush(busy_heap, (end_t, c_idx))
        else:
            if max_queue is not None and len(queue) >= max_queue:
                balked += 1
            else:
                queue.append((arr, srv))
                if len(queue) > max_q_len:
                    max_q_len = len(queue)

    # Дообслуживаем оставшихся в очереди после прихода последнего покупателя
    advance_to(float("inf"))

    avg_wait = (total_wait / served) if served > 0 else 0.0
    avg_srv = (total_service / served) if served > 0 else 0.0
    if min_wait is None:
        min_wait = 0.0

    work_duration = max(close_time or 0.0, last_finish)
    cashier_loads: list[tuple[int, int]] = []
    for i in range(num_cashiers):
        load_pct = (cashier_busy[i] / work_duration * 100.0) if work_duration > 0 else 0.0
        cashier_loads.append((cashier_served[i], int(float(f"{load_pct:.0f}"))))

    return {
        "arrived": arrived,
        "served": served,
        "balked": balked,
        "avg_wait": avg_wait,
        "max_wait": max_wait,
        "min_wait": min_wait,
        "max_q_len": max_q_len,
        "avg_srv": avg_srv,
        "cashiers": cashier_loads,
    }


def format_report(stats: dict, seed: Optional[int]) -> str:
    header = f"Результаты симуляции (семя: {seed}):" if seed is not None else "Результаты симуляции:"
    lines = [
        header,
        "",
        "Общая статистика:",
        f"  Всего пришло покупателей: {fmt_int(stats['arrived'])}",
        f"  Обслужено покупателей: {fmt_int(stats['served'])}",
        f"  Ушло из-за длинной очереди: {fmt_int(stats['balked'])}",
        "",
        "Время ожидания:",
        f"  Среднее время ожидания: {stats['avg_wait']:.1f} мин",
        f"  Максимальное время ожидания: {stats['max_wait']:.1f} мин",
        f"  Минимальное время ожидания: {stats['min_wait']:.1f} мин",
        "",
        "Очередь:",
        f"  Максимальная длина очереди: {fmt_int(stats['max_q_len'])} {plural_person(stats['max_q_len'])}",
        f"  Среднее время обслуживания: {stats['avg_srv']:.1f} мин на покупателя",
        "",
        "Загрузка кассиров:",
    ]

    if not stats["cashiers"]:
        lines.append("  кассиров нет")
    else:
        for idx, (cnt, load) in enumerate(stats["cashiers"], 1):
            lines.append(
                f"  Кассир {idx}: обслужил {fmt_int(cnt)} {plural_customer(cnt)}, загрузка {load}%"
            )

    return "\n".join(lines)


def main() -> int:
    try:
        cfg = parse_args(sys.argv[1:])
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2

    if cfg["seed"] is not None:
        people = generate_customers(
            cfg["seed"], cfg["minutes"], cfg["interval"], cfg["service_range"]
        )
        close_t = cfg["minutes"]
    else:
        people = read_customers_stdin()
        close_t = cfg["close_time"]

    stats = run_simulation(people, cfg["cashiers"], cfg["max_queue"], close_t)
    print(format_report(stats, cfg["seed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())