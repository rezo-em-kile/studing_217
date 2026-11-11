import re
import sys
from dataclasses import dataclass

LINE_RE = re.compile(
    r"^\s*(?P<name>[^:]*?)\s*:\s*"
    r"прибытие\s+(?P<arr>\S+?)\s*,\s*"
    r"отправление\s+(?P<dep>\S+?)\s*$",
    re.IGNORECASE,
)

TIME_RE = re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2})$")


@dataclass
class Train:
    name: str
    arr_min: int
    dep_min: int
    arr_str: str
    dep_str: str
    order: int


def parse_time(raw: str, is_departure: bool, line_no: int, train_name: str) -> tuple[int, str]:
    match = TIME_RE.match(raw)
    if not match:
        raise ValueError(f"строка {line_no} ({train_name}): некорректное время '{raw}'")

    h = int(match.group("h"))
    m = int(match.group("m"))

    if is_departure and h == 24 and m == 0:
        return 1440, "24:00"

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"строка {line_no} ({train_name}): время вне диапазона '{raw}'")

    return h * 60 + m, f"{h:02d}:{m:02d}"


def parse_schedule(lines: list[str]) -> list[Train]:
    trains: list[Train] = []
    seen_names: set[str] = set()

    for line_no, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = LINE_RE.match(raw_line)
        if not match:
            raise ValueError(f"строка {line_no}: неверный формат записи")

        name = match.group("name").strip()
        if not name:
            raise ValueError(f"строка {line_no}: пустое название поезда")

        if name in seen_names:
            raise ValueError(f"строка {line_no}: дублирующееся название поезда '{name}'")
        seen_names.add(name)

        arr_raw = match.group("arr")
        dep_raw = match.group("dep")

        arr_min, arr_str = parse_time(arr_raw, is_departure=False, line_no=line_no, train_name=name)
        dep_min, dep_str = parse_time(dep_raw, is_departure=True, line_no=line_no, train_name=name)

        if dep_min < arr_min:
            dep_min += 1440

        stay = dep_min - arr_min
        if stay <= 0:
            raise ValueError(f"строка {line_no} ({name}): нулевое время стоянки ({arr_raw} - {dep_raw})")
        if stay > 120:
            raise ValueError(f"строка {line_no} ({name}): стоянка больше 2 часов ({arr_raw} - {dep_raw})")

        trains.append(
            Train(
                name=name,
                arr_min=arr_min,
                dep_min=dep_min,
                arr_str=arr_str,
                dep_str=dep_str,
                order=len(trains),
            )
        )

    return trains


def allocate_platforms(trains: list[Train]) -> list[list[Train]]:
    sorted_trains = sorted(trains, key=lambda t: (t.arr_min, t.order))
    platforms: list[list[Train]] = []
    platform_free_time: list[int] = []

    for train in sorted_trains:
        placed = False
        for i, free_time in enumerate(platform_free_time):
            if free_time <= train.arr_min:
                platforms[i].append(train)
                platform_free_time[i] = train.dep_min
                placed = True
                break
        if not placed:
            platforms.append([train])
            platform_free_time.append(train.dep_min)

    return platforms


def format_report(platforms: list[list[Train]]) -> str:
    if not platforms:
        return "Минимальное количество платформ: 0"

    lines = [
        f"Минимальное количество платформ: {len(platforms)}",
        "",
        "Распределение по платформам:",
    ]
    for idx, p_trains in enumerate(platforms, 1):
        items = ", ".join(f"{t.name} ({t.arr_str}\u2013{t.dep_str})" for t in p_trains)
        lines.append(f"  Платформа {idx}: {items}")

    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if len(args) > 1:
        print("Ошибка: слишком много аргументов командной строки", file=sys.stderr)
        return 2

    try:
        if len(args) == 1:
            filename = args[0]
            try:
                with open(filename, "r", encoding="utf-8-sig") as f:
                    lines = f.readlines()
            except OSError as e:
                print(f"Ошибка: не удалось открыть файл '{filename}': {e}", file=sys.stderr)
                return 1
        else:
            text = sys.stdin.read()
            if text.startswith("\ufeff"):
                text = text[1:]
            lines = text.splitlines()

        trains = parse_schedule(lines)
        platforms = allocate_platforms(trains)
        print(format_report(platforms))
        return 0

    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())