"""Расписание поездов: минимальное количество платформ и распределение поездов по ним.

Запуск: python trains.py schedule.txt  или  python trains.py < schedule.txt
"""
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
