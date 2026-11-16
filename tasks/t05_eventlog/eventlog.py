import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

LINE_RE = re.compile(
    r"^[ \t]*"
    r"(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})"
    r"[ T]"
    r"(?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})"
    r"(?P<tz>Z|[+-]\d{2}:?\d{2})?"
    r"[ \t]*(?P<sep>[|;\t])[ \t]*"
    r"(?P<rest>.*)$"
)

TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
CODE_RE = re.compile(r'(?:^|,\s*)code\s*=\s*(?:"([^"]*)"|([^,\s]*))')

EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def fmt_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} Б"
    kb = num_bytes / 1024.0
    if kb < 1024.0:
        return f"{kb:.1f} КБ"
    mb = kb / 1024.0
    return f"{mb:.1f} МБ"


def plural_event(n: int) -> str:
    rem100 = n % 100
    rem10 = n % 10
    if 11 <= rem100 <= 14:
        return "событий"
    if rem10 == 1:
        return "событие"
    if rem10 in (2, 3, 4):
        return "события"
    return "событий"


def plural_error(n: int) -> str:
    rem100 = n % 100
    rem10 = n % 10
    if 11 <= rem100 <= 14:
        return "ошибок"
    if rem10 == 1:
        return "ошибка"
    if rem10 in (2, 3, 4):
        return "ошибки"
    return "ошибок"


def parse_args(argv: list[str]) -> tuple[str, int, int]:
    file_path: Optional[str] = None
    bucket = 60
    gap = 30
    seen_bucket = False
    seen_gap = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--bucket":
            if seen_bucket or i + 1 >= len(argv):
                raise SystemExit("Ошибка: некорректный параметр --bucket")
            seen_bucket = True
            raw = argv[i + 1]
            if not raw or "." in raw:
                raise SystemExit(f"Ошибка: некорректное значение --bucket '{raw}'")
            try:
                bucket = int(raw)
            except ValueError:
                raise SystemExit(f"Ошибка: некорректное значение --bucket '{raw}'")
            if bucket <= 0 or bucket > 1440 or 1440 % bucket != 0:
                raise SystemExit("Ошибка: сутки (1440 мин) должны делиться на --bucket без остатка")
            i += 2
        elif arg == "--gap":
            if seen_gap or i + 1 >= len(argv):
                raise SystemExit("Ошибка: некорректный параметр --gap")
            seen_gap = True
            raw = argv[i + 1]
            if not raw or "." in raw:
                raise SystemExit(f"Ошибка: некорректное значение --gap '{raw}'")
            try:
                gap = int(raw)
            except ValueError:
                raise SystemExit(f"Ошибка: некорректное значение --gap '{raw}'")
            if gap < 0:
                raise SystemExit("Ошибка: параметр --gap должен быть >= 0")
            i += 2
        elif arg.startswith("-"):
            raise SystemExit(f"Ошибка: неизвестный параметр '{arg}'")
        else:
            if file_path is not None:
                raise SystemExit(f"Ошибка: лишний аргумент '{arg}'")
            file_path = arg
            i += 1

    if file_path is None:
        raise SystemExit("Ошибка: не указан файл журнала")

    return file_path, bucket, gap


def parse_line(raw_line: str) -> Optional[tuple[datetime, str, str]]:
    clean = raw_line.rstrip("\r\n")
    m = LINE_RE.match(clean)
    if not m:
        return None

    try:
        y = int(m.group("y"))
        mo = int(m.group("mo"))
        d = int(m.group("d"))
        h = int(m.group("h"))
        mi = int(m.group("mi"))
        s = int(m.group("s"))
        dt = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
    except ValueError:
        return None

    tz_raw = m.group("tz")
    if tz_raw and tz_raw != "Z":
        sign = 1 if tz_raw[0] == "+" else -1
        digits = tz_raw[1:].replace(":", "")
        tz_h = int(digits[:2])
        tz_m = int(digits[2:])
        if tz_h > 14 or tz_m > 59:
            return None
        offset = timedelta(hours=tz_h, minutes=tz_m) * sign
        dt = dt - offset

    sep = m.group("sep")
    rest = m.group("rest")

    if sep in rest:
        ev_type_raw, desc_raw = rest.split(sep, 1)
        ev_type = ev_type_raw.strip()
        desc = desc_raw.strip()
    else:
        ev_type = rest.strip()
        desc = ""
        for other_sep in ("|", ";", "\t"):
            if other_sep != sep and other_sep in ev_type:
                return None

    if not TYPE_RE.match(ev_type):
        return None

    return dt, ev_type.upper(), desc


def extract_codes(desc: str) -> list[str]:
    if not desc or "code" not in desc:
        return []
    codes: list[str] = []
    for m in CODE_RE.finditer(desc):
        val = m.group(1) if m.group(1) is not None else m.group(2)
        if val:
            codes.append(val)
    return codes


def fmt_dt(dt: datetime, multi_day: bool) -> str:
    if multi_day:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.strftime("%H:%M:%S")


def fmt_bucket_range(bucket_idx: int, bucket_mins: int, multi_day: bool) -> str:
    start_dt = EPOCH_UTC + timedelta(minutes=bucket_idx * bucket_mins)
    end_dt = start_dt + timedelta(minutes=bucket_mins)
    if multi_day:
        return f"{start_dt:%Y-%m-%d %H:%M}\u2013{end_dt:%H:%M}"
    return f"{start_dt:%H:%M}\u2013{end_dt:%H:%M}"


def analyze_file(file_path: str, bucket_mins: int, gap_mins: int) -> str:
    try:
        file_size = os.path.getsize(file_path)
        f = open(file_path, "r", encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"Ошибка: не удалось открыть файл '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)

    total_non_empty = 0
    parsed_count = 0
    broken_count = 0
    broken_examples: list[tuple[int, str]] = []
    out_of_order_count = 0

    type_counts: dict[str, int] = {}
    bucket_counts: dict[int, int] = {}

    min_dt: Optional[datetime] = None
    max_dt: Optional[datetime] = None

    gaps: list[tuple[datetime, datetime, int]] = []
    gap_threshold_secs = gap_mins * 60

    # Состояние текущей серии ERROR
    err_streak = 0
    err_start: Optional[datetime] = None
    err_end: Optional[datetime] = None
    err_codes: set[str] = set()
    error_series: list[tuple[datetime, datetime, int, list[str]]] = []

    def flush_error_series() -> None:
        nonlocal err_streak, err_start, err_end, err_codes
        if err_streak >= 3 and err_start is not None and err_end is not None:
            error_series.append((err_start, err_end, err_streak, sorted(err_codes)))
        err_streak = 0
        err_start = None
        err_end = None
        err_codes.clear()

    with f:
        for line_no, raw_line in enumerate(f, 1):
            if line_no == 1 and raw_line.startswith("\ufeff"):
                raw_line = raw_line[1:]

            stripped = raw_line.strip()
            if not stripped:
                continue

            total_non_empty += 1
            parsed = parse_line(raw_line)
            if parsed is None:
                broken_count += 1
                if len(broken_examples) < 10:
                    broken_examples.append((line_no, raw_line.rstrip("\r\n")))
                continue

            dt, ev_type, desc = parsed
            parsed_count += 1
            type_counts[ev_type] = type_counts.get(ev_type, 0) + 1

            mins_since_epoch = int((dt - EPOCH_UTC).total_seconds() // 60)
            b_idx = mins_since_epoch // bucket_mins
            bucket_counts[b_idx] = bucket_counts.get(b_idx, 0) + 1

            if min_dt is None or dt < min_dt:
                min_dt = dt

            if max_dt is None:
                max_dt = dt
            elif dt < max_dt:
                out_of_order_count += 1
            else:
                diff_secs = int((dt - max_dt).total_seconds())
                if diff_secs > gap_threshold_secs:
                    gaps.append((max_dt, dt, diff_secs // 60))
                max_dt = dt

            if ev_type == "ERROR":
                if err_streak == 0:
                    err_start = dt
                err_streak += 1
                err_end = dt
                for c in extract_codes(desc):
                    err_codes.add(c)
            else:
                flush_error_series()

    flush_error_series()

    base_name = os.path.basename(file_path)
    out: list[str] = [
        f"Отчёт по файлу {base_name}:",
        f"  Размер файла: {fmt_size(file_size)}",
        f"  Всего строк: {fmt_int(total_non_empty)}",
        f"  Успешно разобрано: {fmt_int(parsed_count)}",
    ]

    if broken_count == 0:
        out.append("  Битых строк: 0")
    else:
        out.append(f"  Битых строк: {fmt_int(broken_count)} (пропущены)")

    if out_of_order_count > 0:
        out.append(f"  Записано не по порядку времени: {fmt_int(out_of_order_count)}")

    if broken_examples:
        out.append("")
        out.append("Примеры битых строк:")
        for l_no, text in broken_examples:
            out.append(f"  строка {l_no}: {text}")

    out.append("")
    out.append("Статистика по типам событий:")
    if not type_counts:
        out.append("  нет событий")
    else:
        name_width = max(len(t) for t in type_counts) + 2
        cnt_width = max(len(fmt_int(c)) for c in type_counts.values())
        for t, cnt in type_counts.items():
            pct = cnt / parsed_count * 100.0
            out.append(
                f"  {t.ljust(name_width)}: {fmt_int(cnt).rjust(cnt_width)} ({pct:.1f}%)"
            )

    multi_day = bool(min_dt and max_dt and min_dt.date() != max_dt.date())

    out.append("")
    out.append("Пики активности:")
    if not bucket_counts or min_dt is None or max_dt is None:
        out.append("  нет данных")
    else:
        first_b = int((min_dt - EPOCH_UTC).total_seconds() // 60) // bucket_mins
        last_b = int((max_dt - EPOCH_UTC).total_seconds() // 60) // bucket_mins
        total_buckets = last_b - first_b + 1

        max_b = first_b
        max_cnt = -1
        min_b = first_b
        min_cnt = parsed_count + 1

        for b in range(first_b, last_b + 1):
            c = bucket_counts.get(b, 0)
            if c > max_cnt:
                max_cnt = c
                max_b = b
            if c < min_cnt:
                min_cnt = c
                min_b = b

        avg_load = parsed_count / total_buckets
        out.append(
            f"  Максимальная нагрузка: {fmt_bucket_range(max_b, bucket_mins, multi_day)} "
            f"({fmt_int(max_cnt)} {plural_event(max_cnt)})"
        )
        out.append(
            f"  Минимальная нагрузка: {fmt_bucket_range(min_b, bucket_mins, multi_day)} "
            f"({fmt_int(min_cnt)} {plural_event(min_cnt)})"
        )
        out.append(f"  Среднее за {bucket_mins} мин: {avg_load:.1f}")

    out.append("")
    out.append(f"Подозрительные промежутки (более {gap_mins} мин без событий):")
    if not gaps:
        out.append("  не обнаружено")
    else:
        for g_start, g_end, mins in gaps:
            out.append(
                f"  {fmt_dt(g_start, multi_day)} \u2013 {fmt_dt(g_end, multi_day)} ({fmt_int(mins)} мин)"
            )

    out.append("")
    out.append("Серии ошибок:")
    if not error_series:
        out.append("  не обнаружено")
    else:
        for s_start, s_end, cnt, codes in error_series:
            codes_part = f" (code={', '.join(codes)})" if codes else ""
            out.append(
                f"  {fmt_dt(s_start, multi_day)}\u2013{fmt_dt(s_end, multi_day)}: "
                f"{fmt_int(cnt)} {plural_error(cnt)} подряд{codes_part} - ВОЗМОЖНЫЙ СБОЙ"
            )

    return "\n".join(out)


def main() -> int:
    try:
        file_path, bucket_mins, gap_mins = parse_args(sys.argv[1:])
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2

    print(analyze_file(file_path, bucket_mins, gap_mins))
    return 0


if __name__ == "__main__":
    sys.exit(main())