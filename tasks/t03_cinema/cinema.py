import sys

SEAT_PRICES = {
    "o": 300,
    "V": 600,
    "D": 300,
}


def fail_init(msg, code=1):
    print(f"Ошибка: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_time_str(raw):
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    hh_str, mm_str = parts
    if len(hh_str) not in (1, 2) or len(mm_str) != 2:
        return None
    if not (hh_str.isdigit() and mm_str.isdigit()):
        return None
    hh = int(hh_str)
    mm = int(mm_str)
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return hh * 60 + mm


def format_time(minutes):
    hh = minutes // 60
    mm = minutes % 60
    return f"{hh:02d}:{mm:02d}"


def load_hall(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line_num, raw_line in enumerate(f, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                row_seats = []
                for ch in stripped:
                    if ch not in SEAT_PRICES and ch != ".":
                        fail_init(f"строка {line_num}: недопустимый символ места '{ch}'", code=1)
                    row_seats.append(ch)
                rows.append(row_seats)
    except OSError:
        fail_init(f"не удалось открыть файл зала '{path}'", code=1)
    except UnicodeDecodeError:
        fail_init(f"файл зала '{path}' должен быть в кодировке UTF-8", code=1)

    if not rows:
        fail_init("файл зала не содержит ни одного ряда", code=1)

    return rows
