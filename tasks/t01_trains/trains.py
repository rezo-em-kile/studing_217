import sys


def error(msg, code=1):
    print(f"Ошибка: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_time(time_str, allow_24, line_num):
    raw = time_str.strip()
    parts = raw.split(":")
    if len(parts) != 2:
        error(f"строка {line_num}: неверный формат времени '{raw}'")

    h_str, m_str = parts

    if not h_str.isdigit() or len(h_str) > 2:
        error(f"строка {line_num}: неверное время '{raw}'")
    if not m_str.isdigit() or len(m_str) != 2:
        error(f"строка {line_num}: неверное время '{raw}'")

    hours = int(h_str)
    minutes = int(m_str)

    if minutes > 59:
        error(f"строка {line_num}: неверное время '{raw}'")

    if hours == 24 and minutes == 0 and allow_24:
        return 24 * 60, "24:00"

    if hours > 23:
        error(f"строка {line_num}: неверное время '{raw}'")

    return hours * 60 + minutes, f"{hours:02d}:{minutes:02d}"


def parse_lines(lines):
    trains = []
    seen_names = set()

    for line_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            error(f"строка {line_num}: отсутствует двоеточие после названия поезда")

        name, rest = line.split(":", 1)
        name = name.strip()
        if not name:
            error(f"строка {line_num}: пустое название поезда")

        if name in seen_names:
            error(f"строка {line_num}: повторяющееся название поезда '{name}'")
        seen_names.add(name)

        if "," not in rest:
            error(f"строка {line_num}: отсутствует запятая между прибытием и отправлением")

        arr_part, dep_part = rest.split(",", 1)
        arr_tokens = arr_part.strip().split()
        dep_tokens = dep_part.strip().split()

        if len(arr_tokens) != 2:
            error(f"строка {line_num}: неверный блок прибытия")
        arr_word, arr_time = arr_tokens
        if arr_word.lower() != "прибытие":
            error(f"строка {line_num}: ожидалось слово 'прибытие'")

        if len(dep_tokens) != 2:
            error(f"строка {line_num}: неверный блок отправления")
        dep_word, dep_time = dep_tokens
        if dep_word.lower() != "отправление":
            error(f"строка {line_num}: ожидалось слово 'отправление'")

        arr_min, arr_fmt = parse_time(arr_time, allow_24=False, line_num=line_num)
        dep_min, dep_fmt = parse_time(dep_time, allow_24=True, line_num=line_num)

        if dep_min < arr_min:
            dep_min += 24 * 60

        stay = dep_min - arr_min
        if stay == 0:
            error(f"строка {line_num}: время отправления совпадает с прибытием для поезда '{name}'")
        if stay > 120:
            error(f"строка {line_num}: поезд '{name}' стоит больше 2 часов")

        trains.append((arr_min, dep_min, name, arr_fmt, dep_fmt))

    return trains


def get_arrival_time(train):
    arr_min, _, _, _, _ = train
    return arr_min


def main():
    if len(sys.argv) > 2:
        error("слишком много аргументов командной строки", code=2)

    if len(sys.argv) == 2:
        _, filename = sys.argv
        try:
            with open(filename, encoding="utf-8") as f:
                trains = parse_lines(f)
        except OSError:
            error(f"не удалось открыть файл '{filename}'")
        except UnicodeDecodeError:
            error(f"файл '{filename}' должен быть в кодировке UTF-8")
    else:
        try:
            trains = parse_lines(sys.stdin)
        except UnicodeDecodeError:
            error("входные данные должны быть в кодировке UTF-8")

    if not trains:
        print("Минимальное количество платформ: 0")
        return

    trains.sort(key=get_arrival_time)

    platform_free_time = []
    platform_trains = []
    min_free_time = None

    for arr_min, dep_min, name, arr_fmt, dep_fmt in trains:
        if min_free_time is not None and min_free_time <= arr_min:
            for i in range(len(platform_free_time)):
                if platform_free_time[i] <= arr_min:
                    platform_free_time[i] = dep_min
                    platform_trains[i].append(f"{name} ({arr_fmt}\u2013{dep_fmt})")
                    break
            min_free_time = min(platform_free_time)
        else:
            platform_free_time.append(dep_min)
            platform_trains.append([f"{name} ({arr_fmt}\u2013{dep_fmt})"])
            if min_free_time is None or dep_min < min_free_time:
                min_free_time = dep_min

    print(f"Минимальное количество платформ: {len(platform_trains)}")
    print()
    print("Распределение по платформам:")
    for i in range(len(platform_trains)):
        trains_list = ", ".join(platform_trains[i])
        print(f"  Платформа {i + 1}: {trains_list}")


if __name__ == "__main__":
    main()
