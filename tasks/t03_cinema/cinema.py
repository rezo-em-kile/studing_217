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
def parse_seat_coords(token):
    if ":" not in token:
        return None
    r_str, c_str = token.split(":", 1)
    if not (r_str.isdigit() and c_str.isdigit()):
        return None
    r = int(r_str)
    c = int(c_str)
    if r <= 0 or c <= 0:
        return None
    return r, c


def main():
    if len(sys.argv) != 2:
        fail_init("ожидается ровно один аргумент: путь к файлу зала", code=2)

    hall_template = load_hall(sys.argv[1])
    current_time = 0
    sessions = {}
    bookings = {}
    next_booking_id = 1

    try:
        lines = sys.stdin.read().splitlines()
    except UnicodeDecodeError:
        fail_init("входные команды должны быть в кодировке UTF-8", code=1)

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split(None, 1)
        cmd = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "time":
            if not rest or len(rest.split()) != 1:
                print("ОШИБКА: неверный формат команды time")
                continue
            new_time = parse_time_str(rest)
            if new_time is None:
                print(f"ОШИБКА: некорректное время '{rest}'")
                continue
            if new_time < current_time:
                print("ОШИБКА: часы не могут идти назад")
                continue
            current_time = new_time
            for sess in sessions.values():
                sess.sync(current_time)
            print(f"Время: {format_time(current_time)}")

        elif cmd == "session":
            s_parts = rest.split()
            if len(s_parts) not in (1, 2):
                print("ОШИБКА: неверный формат команды session")
                continue
            s_name = s_parts[0]
            if s_name in sessions:
                print(f"ОШИБКА: сеанс {s_name} уже существует")
                continue
            start_t = None
            if len(s_parts) == 2:
                start_t = parse_time_str(s_parts[1])
                if start_t is None:
                    print(f"ОШИБКА: некорректное время начала сеанса '{s_parts[1]}'")
                    continue
            sessions[s_name] = Session(s_name, hall_template, start_t)
            if start_t is None:
                print(f"Сеанс {s_name} добавлен")
            else:
                print(f"Сеанс {s_name} добавлен (начало в {format_time(start_t)})")

        elif cmd == "book":
            b_parts = rest.split(None, 2)
            if len(b_parts) < 3:
                print("ОШИБКА: неверный формат команды book")
                continue
            s_name, coords_raw, user = b_parts[0], b_parts[1], b_parts[2].strip()
            if not user:
                print("ОШИБКА: не указано имя пользователя")
                continue
            if s_name not in sessions:
                print(f"ОШИБКА: сеанс {s_name} не найден")
                continue

            sess = sessions[s_name]
            sess.sync(current_time)

            if sess.start_time is not None and current_time >= sess.start_time:
                print(f"ОШИБКА: бронирование на сеанс {s_name} закрыто")
                continue

            coord_tokens = coords_raw.split(",")
            parsed_coords = []
            seen_coords = set()
            valid_batch = True
            err_msg = ""

            for tok in coord_tokens:
                if not tok:
                    valid_batch = False
                    err_msg = "пустой элемент в списке мест"
                    break
                rc = parse_seat_coords(tok)
                if rc is None:
                    valid_batch = False
                    err_msg = f"некорректные координаты '{tok}'"
                    break
                r, c = rc
                if r > len(sess.hall) or c > len(sess.hall[r - 1]):
                    valid_batch = False
                    err_msg = f"ряд {r}, место {c} не существует"
                    break
                if sess.hall[r - 1][c - 1] == ".":
                    valid_batch = False
                    err_msg = f"ряд {r}, место {c} является проходом"
                    break
                if rc in seen_coords:
                    valid_batch = False
                    err_msg = f"ряд {r}, место {c} указано дважды"
                    break
                if rc in sess.occupied:
                    valid_batch = False
                    err_msg = f"ряд {r}, место {c} уже забронировано"
                    break
                seen_coords.add(rc)
                parsed_coords.append(rc)

            if not valid_batch:
                print(f"ОШИБКА: {err_msg}")
                continue

            for r, c in parsed_coords:
                seat_type = sess.hall[r - 1][c - 1]
                price = SEAT_PRICES[seat_type]
                booking = Booking(next_booking_id, user, s_name, r, c, price, current_time)
                bookings[next_booking_id] = booking
                sess.occupied[(r, c)] = booking
                sess.history.append(booking)
                print(f"Бронь {next_booking_id}: {user}, сеанс {s_name}, ряд {r}, место {c}, {price} руб. - УСПЕШНО")
                next_booking_id += 1

        elif cmd == "pay":
            p_parts = rest.split(None, 1)
            if len(p_parts) < 2 or not p_parts[0].isdigit():
                print("ОШИБКА: неверный формат команды pay")
                continue
            b_id = int(p_parts[0])
            user = p_parts[1].strip()
            if b_id not in bookings:
                print(f"ОШИБКА: бронь {b_id} не найдена")
                continue
            booking = bookings[b_id]
            sessions[booking.session_name].sync(current_time)
            if booking.user != user:
                print(f"ОШИБКА: бронь {b_id} принадлежит другому пользователю")
                continue
            if booking.status == "expired":
                print(f"ОШИБКА: время оплаты брони {b_id} истекло")
                continue
            if booking.status == "cancelled":
                print(f"ОШИБКА: бронь {b_id} уже отменена")
                continue
            if booking.status == "paid":
                print(f"ОШИБКА: бронь {b_id} уже оплачена")
                continue
            booking.status = "paid"
            booking.status_time = current_time
            print(f"Бронь {b_id} оплачена")

        elif cmd == "cancel":
            c_parts = rest.split(None, 1)
            if len(c_parts) < 2 or not c_parts[0].isdigit():
                print("ОШИБКА: неверный формат команды cancel")
                continue
            b_id = int(c_parts[0])
            user = c_parts[1].strip()
            if b_id not in bookings:
                print(f"ОШИБКА: бронь {b_id} не найдена")
                continue
            booking = bookings[b_id]
            sess = sessions[booking.session_name]
            sess.sync(current_time)
            if booking.user != user:
                print(f"ОШИБКА: бронь {b_id} принадлежит другому пользователю")
                continue
            if booking.status == "expired":
                print(f"ОШИБКА: бронь {b_id} уже истекла")
                continue
            if booking.status == "cancelled":
                print(f"ОШИБКА: бронь {b_id} уже отменена")
                continue
            booking.status = "cancelled"
            booking.status_time = current_time
            key = (booking.row, booking.seat)
            if sess.occupied.get(key) is booking:
                del sess.occupied[key]
            print(f"Бронь {b_id} отменена")

        elif cmd == "show":
            s_parts = rest.split()
            if len(s_parts) != 1:
                print("ОШИБКА: неверный формат команды show")
                continue
            s_name = s_parts[0]
            if s_name not in sessions:
                print(f"ОШИБКА: сеанс {s_name} не найден")
                continue
            sess = sessions[s_name]
            sess.sync(current_time)
            print(sess.render_hall())

        elif cmd == "free":
            s_parts = rest.split()
            if len(s_parts) != 1:
                print("ОШИБКА: неверный формат команды free")
                continue
            s_name = s_parts[0]
            if s_name not in sessions:
                print(f"ОШИБКА: сеанс {s_name} не найден")
                continue
            sess = sessions[s_name]
            sess.sync(current_time)
            print(f"Свободно мест: {sess.free_seats()} из {sess.total_seats()}")

        elif cmd == "history":
            s_parts = rest.split()
            if len(s_parts) != 1:
                print("ОШИБКА: неверный формат команды history")
                continue
            s_name = s_parts[0]
            if s_name not in sessions:
                print(f"ОШИБКА: сеанс {s_name} не найден")
                continue
            sess = sessions[s_name]
            sess.sync(current_time)
            if not sess.history:
                print("История пуста")
                continue
            for b in sess.history:
                t_created = format_time(b.created_at)
                if b.status == "active":
                    st_text = "(активно)"
                elif b.status == "paid":
                    st_text = "(оплачено)"
                elif b.status == "cancelled":
                    st_text = f"(отменено в {format_time(b.status_time)})"
                else:
                    st_text = f"(истекло в {format_time(b.status_time)})"
                print(f"{t_created} {b.user} -> ряд {b.row}, место {b.seat} {st_text}")

        else:
            print(f"ОШИБКА: неизвестная команда '{cmd}'")


if __name__ == "__main__":
    main()
