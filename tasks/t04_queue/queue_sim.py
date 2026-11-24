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
    seen_flags = set()
    random_only_used = False

    it = iter(argv)
    for arg in it:
        if arg in seen_flags:
            fail_init(f"повторяющийся параметр '{arg}'", code=2)
        seen_flags.add(arg)

        if arg == "--cashiers":
            val_raw = next(it, None)
            if val_raw is None:
                fail_init("не указано значение для --cashiers", code=2)
            cashiers = parse_non_neg_int(val_raw, "--cashiers")
        elif arg == "--max-queue":
            val_raw = next(it, None)
            if val_raw is None:
                fail_init("не указано значение для --max-queue", code=2)
            if val_raw.lower() == "none":
                max_queue = None
            else:
                max_queue = parse_non_neg_int(val_raw, "--max-queue")
        elif arg == "--close":
            val_raw = next(it, None)
            if val_raw is None:
                fail_init("не указано значение для --close", code=2)
            close_time = parse_pos_float(val_raw, "--close", allow_zero=True)
        elif arg == "--seed":
            val_raw = next(it, None)
            if val_raw is None:
                fail_init("не указано значение для --seed", code=2)
            try:
                seed = int(val_raw)
            except ValueError:
                fail_init("параметр --seed должен быть целым числом", code=2)
        elif arg == "--minutes":
            val_raw = next(it, None)
            if val_raw is None:
                fail_init("не указано значение для --minutes", code=2)
            minutes = parse_pos_float(val_raw, "--minutes", allow_zero=True)
            random_only_used = True
        elif arg == "--interval":
            val_raw = next(it, None)
            if val_raw is None:
                fail_init("не указано значение для --interval", code=2)
            interval = parse_pos_float(val_raw, "--interval", allow_zero=False)
            random_only_used = True
        elif arg == "--service":
            val_raw = next(it, None)
            if val_raw is None:
                fail_init("не указано значение для --service", code=2)
            parts = val_raw.split("-")
            if len(parts) != 2:
                fail_init("параметр --service должен иметь формат МИН-МАКС", code=2)
            s_min_str, s_max_str = parts
            service_min = parse_pos_float(s_min_str, "--service (мин)", allow_zero=False)
            service_max = parse_pos_float(s_max_str, "--service (макс)", allow_zero=False)
            if service_min > service_max:
                fail_init("минимальное время обслуживания больше максимального", code=2)
            random_only_used = True
        else:
            fail_init(f"неизвестный параметр '{arg}'", code=2)

    if seed is None and random_only_used:
        fail_init("параметры --minutes, --interval и --service требуют --seed", code=2)

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
        if arrival < 0 or service <= 0:
            fail_init(f"строка {line_num}: время прихода должно быть >= 0, обслуживания > 0", code=1)
        customers.append((arrival, len(customers), service))

    customers.sort(key=lambda item: (item.__getitem__(0), item.__getitem__(1)))
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
def run_simulation(customers, num_cashiers, max_queue, close_time):
    free_cashiers = list(range(num_cashiers))
    heapq.heapify(free_cashiers)
    busy_cashiers = []
    wait_queue = deque()

    cashier_served = [0 for _ in range(num_cashiers)]
    cashier_busy_time = [0.0 for _ in range(num_cashiers)]

    total_arrived = 0
    total_served = 0
    total_left = 0
    wait_times = []
    service_times = []
    max_q_len = 0
    last_finish_time = 0.0

    def release_until(target_time):
        nonlocal total_served, last_finish_time
        while busy_cashiers:
            top_item = next(iter(busy_cashiers))
            earliest_end, c_idx, srv_dur = top_item
            if earliest_end > target_time:
                break
            heapq.heappop(busy_cashiers)
            cashier_served[c_idx] += 1
            cashier_busy_time[c_idx] += srv_dur
            total_served += 1
            if earliest_end > last_finish_time:
                last_finish_time = earliest_end
            if wait_queue:
                arr_t, next_srv = wait_queue.popleft()
                wait_times.append(earliest_end - arr_t)
                service_times.append(next_srv)
                heapq.heappush(busy_cashiers, (earliest_end + next_srv, c_idx, next_srv))
            else:
                heapq.heappush(free_cashiers, c_idx)

    for arr_t, srv_dur in customers:
        if close_time is not None and arr_t >= close_time:
            break
        release_until(arr_t)
        total_arrived += 1

        if num_cashiers == 0:
            total_left += 1
            continue

        if free_cashiers:
            c_idx = heapq.heappop(free_cashiers)
            wait_times.append(0.0)
            service_times.append(srv_dur)
            heapq.heappush(busy_cashiers, (arr_t + srv_dur, c_idx, srv_dur))
        else:
            if max_queue is not None and len(wait_queue) >= max_queue:
                total_left += 1
            else:
                wait_queue.append((arr_t, srv_dur))
                if len(wait_queue) > max_q_len:
                    max_q_len = len(wait_queue)

    release_until(float("inf"))

    work_duration = max(close_time, last_finish_time) if close_time is not None else last_finish_time

    return {
        "total_arrived": total_arrived,
        "total_served": total_served,
        "total_left": total_left,
        "wait_times": wait_times,
        "service_times": service_times,
        "max_q_len": max_q_len,
        "cashier_served": cashier_served,
        "cashier_busy_time": cashier_busy_time,
        "work_duration": work_duration,
    }


def main():
    _, *raw_args = sys.argv
    cfg = parse_args(raw_args)
    if cfg["seed"] is not None:
        customers = generate_customers(
            cfg["seed"],
            cfg["minutes"],
            cfg["interval"],
            cfg["service_min"],
            cfg["service_max"],
        )
        close_t = cfg["minutes"]
        print(f"Результаты симуляции (семя: {cfg['seed']}):")
    else:
        customers = read_customers_stdin()
        close_t = cfg["close_time"]
        print("Результаты симуляции:")

    stats = run_simulation(customers, cfg["cashiers"], cfg["max_queue"], close_t)

    arrived = stats["total_arrived"]
    served = stats["total_served"]
    left = stats["total_left"]
    waits = stats["wait_times"]
    srvs = stats["service_times"]

    avg_wait = (sum(waits) / len(waits)) if waits else 0.0
    max_wait = max(waits) if waits else 0.0
    min_wait = min(waits) if waits else 0.0
    avg_srv = (sum(srvs) / len(srvs)) if srvs else 0.0
    max_q = stats["max_q_len"]

    print()
    print("Общая статистика:")
    print(f"  Всего пришло покупателей: {format_int(arrived)}")
    print(f"  Обслужено покупателей: {format_int(served)}")
    print(f"  Ушло из-за длинной очереди: {format_int(left)}")
    print()
    print("Время ожидания:")
    print(f"  Среднее время ожидания: {avg_wait:.1f} мин")
    print(f"  Максимальное время ожидания: {max_wait:.1f} мин")
    print(f"  Минимальное время ожидания: {min_wait:.1f} мин")
    print()
    print("Очередь:")
    q_word = plural_ru(max_q, "человек", "человека", "человек")
    print(f"  Максимальная длина очереди: {format_int(max_q)} {q_word}")
    print(f"  Среднее время обслуживания: {avg_srv:.1f} мин на покупателя")
    print()
    print("Загрузка кассиров:")
    if cfg["cashiers"] == 0:
        print("  кассиров нет")
    else:
        dur = stats["work_duration"]
        for idx in range(cfg["cashiers"]):
            c_cnt = stats["cashier_served"][idx]
            c_word = plural_ru(c_cnt, "покупателя", "покупателей", "покупателей")
            load_pct = (stats["cashier_busy_time"][idx] / dur * 100.0) if dur > 0 else 0.0
            print(f"  Кассир {idx + 1}: обслужил {format_int(c_cnt)} {c_word}, загрузка {load_pct:.0f}%")


if __name__ == "__main__":
    main()
