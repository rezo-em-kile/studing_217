"""Бронирование мест в кинозале.

Запуск: python cinema.py ЗАЛ.txt < commands.txt
Команды: time, session, book, pay, cancel, show, free, history (см. README задачи).
"""
import re
import sys

PRICES = {"o": 300, "V": 600, "D": 300}
AISLE = "."
HOLD_MINUTES = 10
MINUTES_IN_DAY = 24 * 60
TIME_RE = re.compile(r"^([0-9]{1,2}):([0-9]{2})$")
SEAT_RE = re.compile(r"^([0-9]+):([0-9]+)$")
NUMBER_RE = re.compile(r"^[0-9]+$")

ACTIVE, PAID, CANCELLED = "активно", "оплачено", "отменено"


class HallError(Exception):
    """Ошибка в файле зала (код 1)."""


class CommandError(Exception):
    """Ошибка в команде: состояние не меняется, работа продолжается."""


def parse_time(text):
    """«ЧЧ:ММ» -> минуты от начала суток или None."""
    match = TIME_RE.match(text)
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def format_time(minutes):
    minutes %= MINUTES_IN_DAY
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def load_hall(path):
    """Читает схему зала: список рядов, ряд - строка символов o/V/D/."""
    try:
        with open(path, encoding="utf-8-sig") as file:
            lines = file.read().splitlines()
    except OSError as error:
        raise HallError(f"не удалось открыть файл зала {path}: {error.strerror}") from None
    except UnicodeDecodeError:
        raise HallError(f"файл зала {path} не в кодировке UTF-8") from None
    rows = []
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        for position, char in enumerate(line, 1):
            if char not in PRICES and char != AISLE:
                raise HallError(f"{path}, строка {number} (ряд {len(rows) + 1}): недопустимый символ "
                                f"«{char}» на позиции {position}, допустимы o, V, D и «.»")
        rows.append(line)
    if not rows:
        raise HallError(f"{path}: в зале нет ни одного ряда")
    if all(char == AISLE for row in rows for char in row):
        raise HallError(f"{path}: в зале нет ни одного места, только проходы")
    return rows


class Booking:
    def __init__(self, number, user, session, row, seat, price, created):
        self.number = number
        self.user = user
        self.session = session
        self.row = row
        self.seat = seat
        self.price = price
        self.created = created
        self.state = ACTIVE
        self.cancelled_at = None

    def expires_at(self):
        return self.created + HOLD_MINUTES

    def status(self, now):
        """Состояние с учётом времени: неоплаченная бронь через 10 минут истекает."""
        if self.state == ACTIVE and now >= self.expires_at():
            return "истекло"
        return self.state

    def holds_seat(self, now):
        return self.status(now) in (ACTIVE, PAID)

    def describe(self, now):
        status = self.status(now)
        if status == "истекло":
            return f"истекло в {format_time(self.expires_at())}"
        if status == CANCELLED:
            return f"отменено в {format_time(self.cancelled_at)}"
        return status


class Session:
    def __init__(self, name, start):
        self.name = name
        self.start = start
        self.bookings = []

    def is_taken(self, row, seat, now):
        return any(b.row == row and b.seat == seat and b.holds_seat(now) for b in self.bookings)


class Cinema:
    def __init__(self, rows):
        self.rows = rows
        self.total_seats = sum(1 for row in rows for char in row if char != AISLE)
        self.now = 0
        self.sessions = {}
        self.bookings = []

    def find_session(self, name):
        if name not in self.sessions:
            raise CommandError(f"сеанса {name} нет")
        return self.sessions[name]

    def find_booking(self, number_text, user):
        if not NUMBER_RE.match(number_text):
            raise CommandError(f"номер брони должен быть целым числом, получено «{number_text}»")
        number = int(number_text)
        if not 1 <= number <= len(self.bookings):
            raise CommandError(f"брони {number} нет")
        booking = self.bookings[number - 1]
        if booking.user != user:
            raise CommandError(f"бронь {number} оформлена на другого пользователя")
        return booking

    def seat_kind(self, row, seat):
        if not 1 <= row <= len(self.rows):
            return None
        line = self.rows[row - 1]
        if not 1 <= seat <= len(line) or line[seat - 1] == AISLE:
            return None
        return line[seat - 1]

    # --- команды ---

    def cmd_time(self, args):
        if len(args) != 1:
            raise CommandError("формат: time ЧЧ:ММ")
        moment = parse_time(args[0])
        if moment is None:
            raise CommandError(f"неверное время «{args[0]}», нужно ЧЧ:ММ от 00:00 до 23:59")
        if moment < self.now:
            raise CommandError(f"время не может идти назад: сейчас {format_time(self.now)}")
        self.now = moment
        return [f"Время: {format_time(moment)}"]

    def cmd_session(self, args):
        if not 1 <= len(args) <= 2:
            raise CommandError("формат: session ИМЯ [ЧЧ:ММ]")
        name = args[0]
        start = None
        if len(args) == 2:
            start = parse_time(args[1])
            if start is None:
                raise CommandError(f"неверное время начала «{args[1]}», нужно ЧЧ:ММ")
        if name in self.sessions:
            raise CommandError(f"сеанс {name} уже есть")
        self.sessions[name] = Session(name, start)
        if start is None:
            return [f"Сеанс {name} добавлен"]
        return [f"Сеанс {name} добавлен (начало в {format_time(start)})"]

    def cmd_book(self, rest):
        parts = rest.split(None, 2)
        if len(parts) < 3 or not parts[2].strip():
            raise CommandError("формат: book СЕАНС РЯД:МЕСТО[,РЯД:МЕСТО…] ИМЯ")
        session = self.find_session(parts[0])
        user = parts[2].strip()
        if session.start is not None and self.now >= session.start:
            raise CommandError(f"сеанс {session.name} уже начался в {format_time(session.start)}, "
                               f"бронировать нельзя")
        seats = []
        for token in parts[1].split(","):
            match = SEAT_RE.match(token)
            if not match:
                raise CommandError(f"неверное место «{token}», нужно РЯД:МЕСТО")
            row, seat = int(match.group(1)), int(match.group(2))
            if self.seat_kind(row, seat) is None:
                raise CommandError(f"ряд {row}, место {seat}: такого места в зале нет")
            if (row, seat) in seats:
                raise CommandError(f"ряд {row}, место {seat} указано дважды")
            if session.is_taken(row, seat, self.now):
                raise CommandError(f"ряд {row}, место {seat} уже забронировано")
            seats.append((row, seat))
        lines = []
        for row, seat in seats:
            booking = Booking(len(self.bookings) + 1, user, session, row, seat,
                              PRICES[self.seat_kind(row, seat)], self.now)
            self.bookings.append(booking)
            session.bookings.append(booking)
            lines.append(f"Бронь {booking.number}: {user}, сеанс {session.name}, ряд {row}, место {seat}, "
                         f"{booking.price} руб. - УСПЕШНО")
        return lines

    def cmd_pay(self, rest):
        parts = rest.split(None, 1)
        if len(parts) < 2:
            raise CommandError("формат: pay НОМЕР ИМЯ")
        booking = self.find_booking(parts[0], parts[1].strip())
        status = booking.status(self.now)
        if status == PAID:
            raise CommandError(f"бронь {booking.number} уже оплачена")
        if status == CANCELLED:
            raise CommandError(f"бронь {booking.number} отменена, оплатить нельзя")
        if status != ACTIVE:
            raise CommandError(f"бронь {booking.number} истекла в {format_time(booking.expires_at())}, "
                               f"оплатить нельзя")
        booking.state = PAID
        return [f"Бронь {booking.number} оплачена"]

    def cmd_cancel(self, rest):
        parts = rest.split(None, 1)
        if len(parts) < 2:
            raise CommandError("формат: cancel НОМЕР ИМЯ")
        booking = self.find_booking(parts[0], parts[1].strip())
        status = booking.status(self.now)
        if status == CANCELLED:
            raise CommandError(f"бронь {booking.number} уже отменена")
        if status not in (ACTIVE, PAID):
            raise CommandError(f"бронь {booking.number} истекла в {format_time(booking.expires_at())}")
        booking.state = CANCELLED
        booking.cancelled_at = self.now
        return [f"Бронь {booking.number} отменена"]

    def cmd_show(self, args):
        session = self.find_session(self.single_name(args, "show"))
        width = len(f"Ряд {len(self.rows)}: ")
        seats = max(len(row) for row in self.rows)
        lines = [(" " * width + "".join(f"{n:<3}" for n in range(1, seats + 1))).rstrip()]
        for row_number, row in enumerate(self.rows, 1):
            cells = []
            for seat_number, char in enumerate(row, 1):
                if char == AISLE:
                    cells.append("   ")
                elif session.is_taken(row_number, seat_number, self.now):
                    cells.append("x  ")
                else:
                    cells.append(f"{char}  ")
            lines.append((f"Ряд {row_number}: ".ljust(width) + "".join(cells)).rstrip())
        return lines

    def cmd_free(self, args):
        session = self.find_session(self.single_name(args, "free"))
        taken = sum(1 for b in session.bookings if b.holds_seat(self.now))
        return [f"Свободно мест: {self.total_seats - taken} из {self.total_seats}"]

    def cmd_history(self, args):
        session = self.find_session(self.single_name(args, "history"))
        if not session.bookings:
            return ["История пуста"]
        return [f"  {format_time(b.created)} {b.user} → ряд {b.row}, место {b.seat} ({b.describe(self.now)})"
                for b in session.bookings]

    @staticmethod
    def single_name(args, command):
        if len(args) != 1:
            raise CommandError(f"формат: {command} СЕАНС")
        return args[0]

    def execute(self, line):
        parts = line.split(None, 1)
        command = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        if command == "time":
            return self.cmd_time(rest.split())
        if command == "session":
            return self.cmd_session(rest.split())
        if command == "book":
            return self.cmd_book(rest)
        if command == "pay":
            return self.cmd_pay(rest)
        if command == "cancel":
            return self.cmd_cancel(rest)
        if command == "show":
            return self.cmd_show(rest.split())
        if command == "free":
            return self.cmd_free(rest.split())
        if command == "history":
            return self.cmd_history(rest.split())
        raise CommandError(f"неизвестная команда «{command}»; есть time, session, book, pay, cancel, "
                           f"show, free, history")


def use_utf8_streams():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main():
    use_utf8_streams()
    if len(sys.argv) != 2:
        print("Ошибка: нужен один аргумент - файл зала; использование: python cinema.py ЗАЛ.txt",
              file=sys.stderr)
        sys.exit(2)
    try:
        cinema = Cinema(load_hall(sys.argv[1]))
    except HallError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        sys.exit(1)
    first = True
    for raw in sys.stdin:
        line = (raw.lstrip("﻿") if first else raw).strip()
        first = False
        if not line:
            continue
        try:
            answer = cinema.execute(line)
        except CommandError as error:
            answer = [f"ОШИБКА: {error}"]
        for text in answer:
            print(text, flush=True)


if __name__ == "__main__":
    main()
