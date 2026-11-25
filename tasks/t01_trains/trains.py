import sys


def heap_push(
    heap: list, item
) -> (
    None
):  # название параметра: тип-аннотация параметров(необязательно для работы кода)

    heap.append(item)
    idx = len(heap) - 1
    while idx > 0:
        parent = (idx - 1) // 2  # индекс родительского элемента
        if heap[idx] < heap[parent]:
            heap[idx], heap[parent] = heap[parent], heap[idx]
            idx = parent
        else:
            break


def heap_pop(heap):
    # Извлекает и возвращает минимальный элемент
    if len(heap) == 1:
        return heap.pop()

    top = heap[0]
    heap[0] = heap.pop()
    idx = 0
    size = len(heap)

    while True:
        left = 2 * idx + 1
        right = 2 * idx + 2
        smallest = idx

        if left < size and heap[left] < heap[smallest]:
            smallest = left
        if right < size and heap[right] < heap[smallest]:
            smallest = right

        if smallest != idx:
            heap[idx], heap[smallest] = heap[smallest], heap[idx]
            idx = smallest
        else:
            break

    return top


def parse_time(time_str: str, is_departure: bool = False) -> tuple[int, str]:
    # Разбирает и проверяет время формата ЧЧ:ММ
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Неверный формат времени '{time_str}'")

    h_str, m_str = parts[0], parts[1]
    if not (1 <= len(h_str) <= 2 and len(m_str) == 2):
        raise ValueError(f"Неверный формат времени '{time_str}'")
    if not (h_str.isdigit() and m_str.isdigit()):
        raise ValueError(f"Время должно состоять из цифр '{time_str}'")

    hours, minutes = int(h_str), int(m_str)

    if not (0 <= minutes <= 59):
        raise ValueError(f"Некорректные минуты в значении '{time_str}'")

    if hours == 24 and minutes == 0:
        if not is_departure:
            raise ValueError("Время прибытия не может быть 24:00")
    elif not (0 <= hours <= 23):
        raise ValueError(f"Некорректные часы в значении '{time_str}'")

    return hours * 60 + minutes, f"{hours:02d}:{minutes:02d}"


def parse_part(part: str, expected_keyword: str) -> str:
    # Извлекает время из фрагмента вида 'прибытие 09:00'
    tokens = part.split()
    if len(tokens) != 2 or tokens[0].lower() != expected_keyword:
        raise ValueError(
            f"Ожидалось '{expected_keyword} ЧЧ:ММ', получено '{part.strip()}'"
        )
    return tokens[1]


def parse_schedule(lines) -> list[dict]:
    # Читает и валидирует расписание без регулярных выражений
    trains = []
    seen_names = set()

    for line_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Делим по первому двоеточию (название поезда двоеточий не содержит)
        if ":" not in line:
            raise ValueError(f"строка {line_num}: отсутствует двоеточие -> '{line}'")

        name_part, rest = line.split(":", 1)
        name = name_part.strip()
        if not name:
            raise ValueError(f"строка {line_num}: пустое название поезда")
        if name in seen_names:
            raise ValueError(
                f"строка {line_num} ({name}): повторяющееся название поезда"
            )
        seen_names.add(name)

        # Делим оставшуюся часть по запятой на прибытие и отправление
        times_parts = rest.split(",")
        if len(times_parts) != 2:
            raise ValueError(
                f"строка {line_num}: неверный разделитель запятая -> '{line}'"
            )

        try:
            arr_str = parse_part(times_parts[0], "прибытие")
            dep_str = parse_part(times_parts[1], "отправление")
            arr_min, arr_fmt = parse_time(arr_str, is_departure=False)
            dep_min, dep_fmt = parse_time(dep_str, is_departure=True)
        except ValueError as err:
            raise ValueError(
                f"строка {line_num} ({name}): {err}"
            ) from None  # frome None скрывает трассировку

        actual_dep_min = dep_min + (24 * 60 if dep_min < arr_min else 0)
        duration = actual_dep_min - arr_min  # длительность стоянки

        if duration == 0:
            raise ValueError(
                f"cтрока {line_num} ({name}): стоянка не может быть нулевой"
            )
        if duration > 120:
            raise ValueError(
                f"cтрока {line_num} ({name}): стоянка превышает 2 часа ({duration} мин)"
            )
        trains.append(
            {
                "index": len(trains),
                "name": name,
                "arr": arr_min,
                "dep": actual_dep_min,
                "arr_fmt": arr_fmt,
                "dep_fmt": dep_fmt,
            }
        )

    return trains


def assign_platforms(
    trains: list[dict],
) -> list[list[str]]:  # list[dict] - список словарей
    # Распределяет поезда по платформам
    if not trains:
        return []

    def get_sort_key(t):
        return (t["arr"], t["index"])

    trains.sort(key=get_sort_key)

    busy_platforms = []
    free_platforms = []
    platforms_schedule: list[list[str]] = []

    for train in trains:
        arr = train["arr"]
        dep = train["dep"]

        while busy_platforms and busy_platforms[0][0] <= arr:
            _, freed_id = heap_pop(busy_platforms)
            heap_push(free_platforms, freed_id)

        if free_platforms:
            platform_id = heap_pop(free_platforms)
        else:
            platform_id = len(platforms_schedule)
            platforms_schedule.append([])

        heap_push(busy_platforms, (dep, platform_id))

        record = f"{train['name']} ({train['arr_fmt']}\u2013{train['dep_fmt']})"
        platforms_schedule[platform_id].append(record)

    return platforms_schedule


def main():

    if len(sys.argv) > 2:
        print(
            "Ошибка: слишком много аргументов. Использование: python trains.py [schedule.txt]",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        if len(sys.argv) == 2:
            with open(sys.argv[1], "r", encoding="utf-8") as file:
                trains = parse_schedule(file)
        else:
            sys.stdin.reconfigure(encoding="utf-8")
            trains = parse_schedule(sys.stdin)

        schedule = assign_platforms(trains)
        count = len(schedule)

        print(f"Минимальное количество платформ: {count}")
        if count > 0:
            print("\nРаспределение по платформам:")
            for idx, records in enumerate(schedule, start=1):
                print(f"  Платформа {idx}: {', '.join(records)}")

    except FileNotFoundError:
        print(f"Ошибка: файл '{sys.argv[1]}' не найден.", file=sys.stderr)
        sys.exit(1)
    except OSError as err:
        print(
            f"Ошибка: не удалось прочитать файл '{sys.argv[1]}': {err}", file=sys.stderr
        )
        sys.exit(1)
    except UnicodeDecodeError:
        print("Ошибка: файл должен быть в кодировке UTF-8.", file=sys.stderr)
        sys.exit(1)
    except ValueError as err:
        print(f"Ошибка: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
