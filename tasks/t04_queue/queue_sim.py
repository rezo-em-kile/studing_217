from collections import deque
import heapq
import math
import random
import sys


def fail_init(msg, code=2):
    print(f"Ошибка: {msg}", file=sys.stderr)
    sys.exit(code)


def format_int(n):
    return f"{n:,}".replace(",", " ")


def plural_ru(n, one, few, many):
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 19:
        return many
    last = n_abs % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def parse_non_neg_int(raw, name):
    try:
        val = int(raw)
    except ValueError:
        fail_init(f"параметр {name} должен быть целым числом", code=2)
    if val < 0:
        fail_init(f"параметр {name} должен быть >= 0", code=2)
    return val


def parse_pos_float(raw, name, allow_zero=False):
    try:
        val = float(raw)
    except ValueError:
        fail_init(f"параметр {name} должен быть числом", code=2)
    if math.isnan(val) or math.isinf(val):
        fail_init(f"параметр {name} должен быть конечным числом", code=2)
    if allow_zero:
        if val < 0:
            fail_init(f"параметр {name} должен быть >= 0", code=2)
    else:
        if val <= 0:
            fail_init(f"параметр {name} должен быть > 0", code=2)
    return val


def parse_args(argv):
    cashiers = 3
    max_queue = 10
    close_time = None
    seed = None
    minutes = 720.0
    interval = 0.5
    service_min = 2.0
    service_max = 5.0

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--cashiers":
            if i + 1 >= len(argv):
                fail_init("не указано значение для --cashiers", code=2)
            cashiers = parse_non_neg_int(argv[i + 1], "--cashiers")
            i += 2
        elif arg == "--max-queue":
            if i + 1 >= len(argv):
                fail_init("не указано значение для --max-queue", code=2)
            val_str = argv[i + 1]
            if val_str.lower() == "none":
                max_queue = None
            else:
                max_queue = parse_non_neg_int(val_str, "--max-queue")
            i += 2
        elif arg == "--close":
            if i + 1 >= len(argv):
                fail_init("не указано значение для --close", code=2)
            close_time = parse_pos_float(argv[i + 1], "--close", allow_zero=True)
            i += 2
        elif arg == "--seed":
            if i + 1 >= len(argv):
                fail_init("не указано значение для --seed", code=2)
            try:
                seed = int(argv[i + 1])
            except ValueError:
                fail_init("параметр --seed должен быть целым числом", code=2)
            i += 2
        elif arg == "--minutes":
            if i + 1 >= len(argv):
                fail_init("не указано значение для --minutes", code=2)
            minutes = parse_pos_float(argv[i + 1], "--minutes", allow_zero=True)
            i += 2
        elif arg == "--interval":
            if i + 1 >= len(argv):
                fail_init("не указано значение для --interval", code=2)
            interval = parse_pos_float(argv[i + 1], "--interval", allow_zero=False)
            i += 2
        elif arg == "--service":
            if i + 1 >= len(argv):
                fail_init("не указано значение для --service", code=2)
            parts = argv[i + 1].split("-")
            if len(parts) != 2:
                fail_init("параметр --service должен иметь формат МИН-МАКС", code=2)
            s_min_str, s_max_str = parts
            service_min = parse_pos_float(s_min_str, "--service (мин)", allow_zero=True)
            service_max = parse_pos_float(s_max_str, "--service (макс)", allow_zero=True)
            if service_min > service_max:
                fail_init("минимальное время обслуживания больше максимального", code=2)
            i += 2
        else:
            fail_init(f"неизвестный параметр '{arg}'", code=2)

    if seed is not None and close_time is not None:
        fail_init("параметр --close недопустим в режиме генерации (--seed)", code=2)

    return {
        "cashiers": cashiers,
        "max_queue": max_queue,
        "close_time": close_time,
        "seed": seed,
        "minutes": minutes,
        "interval": interval,
        "service_min": service_min,
        "service_max": service_max,
    }


def read_customers_stdin():
    customers = []
    try:
        raw_text = sys.stdin.read()
    except UnicodeDecodeError:
        fail_init("входные данные должны быть в кодировке UTF-8", code=1)

    for line_num, raw_line in enumerate(raw_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) != 2:
            fail_init(f"строка {line_num}: ожидается два числа (приход и обслуживание)", code=1)
        arr_str, srv_str = parts
        try:
            arrival = float(arr_str)
            service = float(srv_str)
        except ValueError:
            fail_init(f"строка {line_num}: некорректный формат числа", code=1)
        if math.isnan(arrival) or math.isinf(arrival) or math.isnan(service) or math.isinf(service):
            fail_init(f"строка {line_num}: числа должны быть конечными", code=1)
        if arrival < 0 or service < 0:
            fail_init(f"строка {line_num}: время не может быть отрицательным", code=1)
        customers.append((arrival, len(customers), service))

    customers.sort(key=lambda item: (item[0], item[1]))
    return [(arr, srv) for arr, _, srv in customers]


def generate_customers(seed, minutes, interval, service_min, service_max):
    rng = random.Random(seed)
    customers = []
    t = 0.0
    while True:
        dt = rng.expovariate(1.0 / interval)
        t += dt
        if t >= minutes:
            break
        srv = rng.uniform(service_min, service_max)
        customers.append((t, srv))
    return customers
