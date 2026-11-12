"""Расписание поездов: минимальное количество платформ и распределение поездов по ним.

Запуск: python trains.py schedule.txt  или  python trains.py < schedule.txt
"""
import heapq
import re
import sys

MINUTES_IN_DAY = 24 * 60
MAX_STAY = 2 * 60

LINE_RE = re.compile(r"^(?P<name>[^:]*):\s*прибытие\s*(?P<arr>.*?)\s*,\s*отправление\s*(?P<dep>.*?)\s*$",
                     re.IGNORECASE)
TIME_RE = re.compile(r"^([0-9]{1,2}):([0-9]{2})$")


class ScheduleError(Exception):
    """Ошибка во входных данных."""


def parse_time(text, allow_midnight_end):
    """Переводит «ЧЧ:ММ» в минуты от начала суток; None, если время записано неверно."""
    match = TIME_RE.match(text)
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if minutes > 59:
        return None
    if hours == 24 and minutes == 0 and allow_midnight_end:
        return MINUTES_IN_DAY
    if hours > 23:
        return None
    return hours * 60 + minutes


def format_time(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_schedule(lines):
    """Разбирает строки расписания в список поездов (имя, прибытие, отправление, тексты времени)."""
    trains = []
    seen_names = set()
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_RE.match(line)
        if not match:
            raise ScheduleError(f"строка {number}: неверный формат, ожидается "
                                f"«Название: прибытие ЧЧ:ММ, отправление ЧЧ:ММ»")
        name = match.group("name").strip()
        arr_text, dep_text = match.group("arr"), match.group("dep")
        if not name:
            raise ScheduleError(f"строка {number}: пустое название поезда")
        if not dep_text:
            raise ScheduleError(f"строка {number}: поезд {name}: не указано время отправления")
        arrival = parse_time(arr_text, allow_midnight_end=False)
        if arrival is None:
            raise ScheduleError(f"строка {number}: поезд {name}: неверное время прибытия «{arr_text}»")
        departure = parse_time(dep_text, allow_midnight_end=True)
        if departure is None:
            raise ScheduleError(f"строка {number}: поезд {name}: неверное время отправления «{dep_text}»")
        if departure == arrival:
            raise ScheduleError(f"строка {number}: поезд {name}: прибытие и отправление совпадают ({arr_text})")
        end = departure if departure > arrival else departure + MINUTES_IN_DAY
        if end - arrival > MAX_STAY:
            raise ScheduleError(f"строка {number}: поезд {name} стоит на платформе больше 2 часов "
                                f"({arr_text}–{dep_text})")
        if name in seen_names:
            raise ScheduleError(f"строка {number}: поезд {name} уже есть в расписании")
        seen_names.add(name)
        trains.append((name, arrival, end, format_time(arrival), format_time(departure)))
    return trains


def assign_platforms(trains):
    """Ставит поезда по порядку прибытия на свободную платформу с наименьшим номером."""
    order = sorted(range(len(trains)), key=lambda i: (trains[i][1], i))
    platforms = []
    free = []
    busy = []
    for index in order:
        _, arrival, end, _, _ = trains[index]
        while busy and busy[0][0] <= arrival:
            heapq.heappush(free, heapq.heappop(busy)[1])
        if free:
            platform = heapq.heappop(free)
        else:
            platform = len(platforms)
            platforms.append([])
        platforms[platform].append(trains[index])
        heapq.heappush(busy, (end, platform))
    return platforms


def build_report(trains):
    platforms = assign_platforms(trains)
    lines = [f"Минимальное количество платформ: {len(platforms)}"]
    if platforms:
        lines.append("")
        lines.append("Распределение по платформам:")
        for number, platform in enumerate(platforms, 1):
            items = ", ".join(f"{name} ({arr}–{dep})" for name, _, _, arr, dep in platform)
            lines.append(f"  Платформа {number}: {items}")
    return lines


def read_input(args):
    if len(args) > 1:
        print("Ошибка: слишком много аргументов, использование: python trains.py [schedule.txt]",
              file=sys.stderr)
        sys.exit(2)
    if args:
        try:
            with open(args[0], encoding="utf-8-sig") as file:
                return file.read()
        except OSError as error:
            raise ScheduleError(f"не удалось открыть файл {args[0]}: {error.strerror}") from None
        except UnicodeDecodeError:
            raise ScheduleError(f"файл {args[0]} не в кодировке UTF-8") from None
    data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ScheduleError("стандартный ввод не в кодировке UTF-8") from None


def use_utf8_output():
    """В консоли Windows по умолчанию не UTF-8 - символ «–» иначе не напечатается."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main():
    use_utf8_output()
    try:
        trains = parse_schedule(read_input(sys.argv[1:]).splitlines())
    except ScheduleError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        sys.exit(1)
    for line in build_report(trains):
        print(line)


if __name__ == "__main__":
    main()
