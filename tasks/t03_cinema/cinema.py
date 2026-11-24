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


class Booking:
    def __init__(self, booking_id, user, session_name, row, seat, price, created_at):
        self.booking_id = booking_id
        self.user = user
        self.session_name = session_name
        self.row = row
        self.seat = seat
        self.price = price
        self.created_at = created_at
        self.status = "active"
        self.status_time = None

    def sync_expiration(self, current_time):
        if self.status == "active" and current_time >= self.created_at + 10:
            self.status = "expired"
            self.status_time = self.created_at + 10


class Session:
    def __init__(self, name, hall_template, start_time=None):
        self.name = name
        self.start_time = start_time
        self.hall = [list(r) for r in hall_template]
        self.occupied = {}
        self.history = []

    def sync(self, current_time):
        for booking in self.history:
            if booking.status == "active":
                booking.sync_expiration(current_time)
                if booking.status == "expired":
                    key = (booking.row, booking.seat)
                    if self.occupied.get(key) is booking:
                        del self.occupied[key]

    def total_seats(self):
        total = 0
        for r in self.hall:
            for ch in r:
                if ch != ".":
                    total += 1
        return total

    def free_seats(self):
        return self.total_seats() - len(self.occupied)

    def render_hall(self):
        max_cols = max(len(r) for r in self.hall)
        num_rows = len(self.hall)
        prefix_width = len(f"Ряд {num_rows}: ")

        col_nums = []
        for c in range(1, max_cols + 1):
            col_nums.append(f"{c:<3}")
        header = (" " * prefix_width + "".join(col_nums)).rstrip()
        lines = [header]

        for r_idx, row in enumerate(self.hall, start=1):
            label = f"Ряд {r_idx}: ".ljust(prefix_width)
            cells = []
            for c_idx, ch in enumerate(row, start=1):
                if ch == ".":
                    disp = " "
                elif (r_idx, c_idx) in self.occupied:
                    disp = "x"
                else:
                    disp = ch
                cells.append(f"{disp:<3}")
            lines.append((label + "".join(cells)).rstrip())

        return "\n".join(lines)
