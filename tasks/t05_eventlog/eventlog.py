"""Анализатор дневника событий.

Запуск: python eventlog.py ФАЙЛ [--bucket МИН] [--gap МИН]

Файл читается потоком, по строке: события не складываются в список, хранятся только
счётчики (по типам и по интервалам), найденные промежутки и серии ошибок.
"""
import os
import re
import sys
from datetime import date

SECONDS_IN_DAY = 24 * 60 * 60
MINUTES_IN_DAY = 24 * 60
MAX_BROKEN_EXAMPLES = 10
SERIES_LENGTH = 3

LINE_RE = re.compile(
    r"^\s*(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})[ T](?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?P<zone>Z|[+-][0-9]{2}:?[0-9]{2})?"
    r"\s*(?P<sep>[|;\t])\s*(?P<type>[A-Za-z][A-Za-z0-9_]*)"
    r"\s*(?:(?P=sep)\s*(?P<description>.*?))?\s*$"
)
FIELD_RE = re.compile(r'\s*([^=,]+?)\s*=\s*("[^"]*"|\'[^\']*\'|[^,]*?)\s*(?:,|$)')


class UsageError(Exception):
    """Неверные аргументы командной строки (код 2)."""


def parse_args(args):
    path = None
    options = {"--bucket": 60, "--gap": 30}
    position = 0
    while position < len(args):
        arg = args[position]
        if arg in options:
            if position + 1 >= len(args):
                raise UsageError(f"после {arg} нужно целое число минут")
            value = args[position + 1]
            if not re.fullmatch(r"[0-9]+", value):
                raise UsageError(f"{arg}: нужно целое число минут, получено «{value}»")
            options[arg] = int(value)
            position += 2
        elif arg.startswith("--"):
            raise UsageError(f"неизвестный параметр {arg}")
        elif path is None:
            path = arg
            position += 1
        else:
            raise UsageError(f"лишний аргумент «{arg}»")
    if path is None:
        raise UsageError("не указан файл журнала")
    bucket = options["--bucket"]
    if bucket <= 0 or MINUTES_IN_DAY % bucket:
        raise UsageError(f"--bucket: сутки (1440 мин) должны делиться на длину интервала без остатка, "
                         f"получено {bucket}")
    return path, bucket, options["--gap"]


def parse_moment(date_text, time_text, zone):
    """Время события в секундах (UTC) от начала эпохи date.toordinal или None, если дата неверна."""
    year, month, day = (int(part) for part in date_text.split("-"))
    hours, minutes, seconds = (int(part) for part in time_text.split(":"))
    if hours > 23 or minutes > 59 or seconds > 59:
        return None
    try:
        ordinal = date(year, month, day).toordinal()
    except ValueError:
        return None
    offset = 0
    if zone and zone != "Z":
        digits = zone[1:].replace(":", "")
        zone_hours, zone_minutes = int(digits[:2]), int(digits[2:])
        if zone_hours > 14 or zone_minutes > 59:
            return None
        offset = (zone_hours * 60 + zone_minutes) * 60
        if zone[0] == "-":
            offset = -offset
    return ordinal * SECONDS_IN_DAY + hours * 3600 + minutes * 60 + seconds - offset


def parse_fields(description):
    """Поля «ключ=значение» из описания (значение можно взять в кавычки)."""
    fields = []
    for match in FIELD_RE.finditer(description or ""):
        value = match.group(2)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields.append((match.group(1), value))
    return fields


def group(number):
    return f"{number:,}".replace(",", " ")


def plural(count, one, few, many):
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def events_text(count):
    return f"{group(count)} {plural(count, 'событие', 'события', 'событий')}"


def size_text(size):
    if size < 1024:
        return f"{size} Б"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} КБ"
    return f"{size / 1024 / 1024:.1f} МБ"


class Analyzer:
    """Накопитель статистики: получает строки по одной."""

    def __init__(self, bucket, gap):
        self.bucket_seconds = bucket * 60
        self.gap_seconds = gap * 60
        self.total = 0
        self.parsed = 0
        self.broken = 0
        self.broken_examples = []
        self.out_of_order = 0
        self.type_counts = {}
        self.bucket_counts = {}
        self.first = None
        self.latest = None
        self.gaps = []
        self.series = []
        self.run_start = None
        self.run_end = None
        self.run_length = 0
        self.run_codes = set()

    def feed(self, number, raw):
        line = raw.strip()
        if not line:
            return
        self.total += 1
        match = LINE_RE.match(line)
        moment = parse_moment(match.group("date"), match.group("time"), match.group("zone")) if match else None
        if moment is None:
            self.broken += 1
            if len(self.broken_examples) < MAX_BROKEN_EXAMPLES:
                self.broken_examples.append((number, raw.rstrip("\r\n")))
            return
        self.parsed += 1
        kind = match.group("type").upper()
        self.type_counts[kind] = self.type_counts.get(kind, 0) + 1
        index = moment // self.bucket_seconds
        self.bucket_counts[index] = self.bucket_counts.get(index, 0) + 1
        if self.first is None or moment < self.first:
            self.first = moment
        if self.latest is not None:
            if moment < self.latest:
                self.out_of_order += 1
            elif moment - self.latest > self.gap_seconds:
                self.gaps.append((self.latest, moment))
        if self.latest is None or moment > self.latest:
            self.latest = moment
        self.track_errors(kind, moment, match.group("description"))

    def track_errors(self, kind, moment, description):
        if kind != "ERROR":
            self.close_series()
            return
        if self.run_length == 0:
            self.run_start = moment
        self.run_end = moment
        self.run_length += 1
        for key, value in parse_fields(description):
            if key == "code" and value:
                self.run_codes.add(value)

    def close_series(self):
        if self.run_length >= SERIES_LENGTH:
            self.series.append((self.run_start, self.run_end, self.run_length, sorted(self.run_codes)))
        self.run_length = 0
        self.run_codes = set()

    # --- отчёт ---

    def multi_day(self):
        return self.first is not None and self.first // SECONDS_IN_DAY != self.latest // SECONDS_IN_DAY

    def moment_text(self, moment):
        seconds = moment % SECONDS_IN_DAY
        clock = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
        if self.multi_day():
            return f"{date.fromordinal(moment // SECONDS_IN_DAY).isoformat()} {clock}"
        return clock

    def interval_text(self, index):
        start = index * self.bucket_seconds
        end = start + self.bucket_seconds

        def hhmm(moment):
            seconds = moment % SECONDS_IN_DAY
            return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}"

        text = f"{hhmm(start)}–{hhmm(end)}"
        if self.multi_day():
            return f"{date.fromordinal(start // SECONDS_IN_DAY).isoformat()} {text}"
        return text

    def report(self, name, size, bucket, gap):
        lines = [
            f"Отчёт по файлу {name}:",
            f"  Размер файла: {size_text(size)}",
            f"  Всего строк: {group(self.total)}",
            f"  Успешно разобрано: {group(self.parsed)}",
            f"  Битых строк: {group(self.broken)}" + (" (пропущены)" if self.broken else ""),
        ]
        if self.out_of_order:
            lines.append(f"  Записано не по порядку времени: {group(self.out_of_order)}")
        if self.broken_examples:
            lines += ["", "Примеры битых строк:"]
            lines += [f"  строка {number}: {text}" for number, text in self.broken_examples]

        lines += ["", "Статистика по типам событий:"]
        if not self.type_counts:
            lines.append("  нет событий")
        else:
            name_width = max(len(kind) for kind in self.type_counts) + 2
            count_width = max(len(group(count)) for count in self.type_counts.values())
            for kind, count in self.type_counts.items():
                share = count / self.parsed * 100
                lines.append(f"  {kind.ljust(name_width)}: {group(count).rjust(count_width)} ({share:.1f}%)")

        lines += ["", "Пики активности:"]
        if not self.bucket_counts:
            lines.append("  нет данных")
        else:
            low, high = min(self.bucket_counts), max(self.bucket_counts)
            busiest = min(self.bucket_counts, key=lambda i: (-self.bucket_counts[i], i))
            quietest = low
            index = low
            while index <= high and index in self.bucket_counts:
                index += 1
            if index <= high:
                quietest = index
            else:
                quietest = min(self.bucket_counts, key=lambda i: (self.bucket_counts[i], i))
            average = self.parsed / (high - low + 1)
            lines.append(f"  Максимальная нагрузка: {self.interval_text(busiest)} "
                         f"({events_text(self.bucket_counts[busiest])})")
            lines.append(f"  Минимальная нагрузка: {self.interval_text(quietest)} "
                         f"({events_text(self.bucket_counts.get(quietest, 0))})")
            lines.append(f"  Среднее за {bucket} мин: {group_float(average)}")

        lines += ["", f"Подозрительные промежутки (более {gap} мин без событий):"]
        if not self.gaps:
            lines.append("  не обнаружено")
        for start, end in self.gaps:
            lines.append(f"  {self.moment_text(start)} – {self.moment_text(end)} ({group((end - start) // 60)} мин)")

        lines += ["", "Серии ошибок:"]
        if not self.series:
            lines.append("  не обнаружено")
        for start, end, length, codes in self.series:
            codes_text = f" (code={', '.join(codes)})" if codes else ""
            lines.append(f"  {self.moment_text(start)}–{self.moment_text(end)}: {group(length)} "
                         f"{plural(length, 'ошибка', 'ошибки', 'ошибок')} подряд{codes_text} - ВОЗМОЖНЫЙ СБОЙ")
        return lines


def group_float(value):
    return f"{value:,.1f}".replace(",", " ")


def use_utf8_streams():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main():
    use_utf8_streams()
    try:
        path, bucket, gap = parse_args(sys.argv[1:])
    except UsageError as error:
        print(f"Ошибка: {error}; использование: python eventlog.py ФАЙЛ [--bucket МИН] [--gap МИН]",
              file=sys.stderr)
        sys.exit(2)
    analyzer = Analyzer(bucket, gap)
    try:
        size = os.path.getsize(path)
        with open(path, encoding="utf-8-sig", errors="replace") as file:
            for number, raw in enumerate(file, 1):
                analyzer.feed(number, raw)
    except OSError as error:
        print(f"Ошибка: не удалось прочитать файл {path}: {error.strerror}", file=sys.stderr)
        sys.exit(1)
    analyzer.close_series()
    for line in analyzer.report(os.path.basename(path), size, bucket, gap):
        print(line)


if __name__ == "__main__":
    main()
