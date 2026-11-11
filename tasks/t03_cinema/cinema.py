import re
import sys
from dataclasses import dataclass, field
from typing import Optional

TIME_RE = re.compile(r"^(?P<h>\d{2}):(?P<m>\d{2})$")
SEAT_RE = re.compile(r"^(?P<r>\d+):(?P<s>\d+)$")


def parse_hhmm(raw: str) -> Optional[int]:
    m = TIME_RE.match(raw)
    if not m:
        return None
    h = int(m.group("h"))
    mins = int(m.group("m"))
    if not (0 <= h <= 23 and 0 <= mins <= 59):
        return None
    return h * 60 + mins


def fmt_hhmm(total_mins: int) -> str:
    return f"{(total_mins // 60) % 24:02d}:{total_mins % 60:02d}"


@dataclass
class Hall:
    rows: list[str]
    total_seats: int
    max_cols: int

    def seat_type(self, r: int, s: int) -> Optional[str]:
        if r < 1 or r > len(self.rows):
            return None
        row_str = self.rows[r - 1]
        if s < 1 or s > len(row_str):
            return None
        ch = row_str[s - 1]
        return None if ch == "." else ch

    def seat_price(self, r: int, s: int) -> int:
        st = self.seat_type(r, s)
        return 600 if st == "V" else 300


@dataclass
class Booking:
    booking_id: int
    session_name: str
    user: str
    row: int
    seat: int
    price: int
    created_at: int
    status: str = "active"  # "active", "paid", "canceled", "expired"
    ended_at: Optional[int] = None

    def check_expiration(self, current_time: int) -> None:
        if self.status == "active" and current_time >= self.created_at + 10:
            self.status = "expired"
            self.ended_at = self.created_at + 10

    def is_occupying(self, current_time: int) -> bool:
        self.check_expiration(current_time)
        return self.status in ("active", "paid")


@dataclass
class Session:
    name: str
    start_time: Optional[int] = None
    bookings: list[Booking] = field(default_factory=list)


def load_hall(path: str) -> Hall:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            raw_lines = f.readlines()
    except OSError as e:
        print(f"Ошибка: не удалось открыть файл зала '{path}': {e}", file=sys.stderr)
        sys.exit(1)

    rows: list[str] = []
    total_seats = 0
    max_cols = 0

    for raw in raw_lines:
        line = raw.strip()
        if not line:
            continue
        row_idx = len(rows) + 1
        for ch in line:
            if ch not in ("o", "V", "D", "."):
                print(
                    f"Ошибка: ряд {row_idx}: недопустимый символ '{ch}' в схеме зала",
                    file=sys.stderr,
                )
                sys.exit(1)
            if ch in ("o", "V", "D"):
                total_seats += 1
        rows.append(line)
        if len(line) > max_cols:
            max_cols = len(line)

    if not rows or total_seats == 0:
        print("Ошибка: в зале нет мест для бронирования", file=sys.stderr)
        sys.exit(1)

    return Hall(rows=rows, total_seats=total_seats, max_cols=max_cols)


class CinemaSystem:
    def __init__(self, hall: Hall):
        self.hall = hall
        self.current_time = 0
        self.sessions: list[Session] = []
        self.all_bookings: list[Booking] = []

    def _find_session(self, name: str) -> Optional[Session]:
        for s in self.sessions:
            if s.name == name:
                return s
        return None

    def _find_booking(self, booking_id: int) -> Optional[Booking]:
        if 1 <= booking_id <= len(self.all_bookings):
            return self.all_bookings[booking_id - 1]
        return None

    def _expire_all(self) -> None:
        for b in self.all_bookings:
            b.check_expiration(self.current_time)

    def _is_seat_taken(self, sess: Session, r: int, s: int) -> bool:
        for b in sess.bookings:
            if b.row == r and b.seat == s and b.is_occupying(self.current_time):
                return True
        return False

    def cmd_time(self, rest: str) -> list[str]:
        parts = rest.split()
        if len(parts) != 1:
            return ["ОШИБКА: неверный формат команды time"]
        new_time = parse_hhmm(parts[0])
        if new_time is None:
            return [f"ОШИБКА: некорректное время '{parts[0]}'"]
        if new_time < self.current_time:
            return ["ОШИБКА: время не может идти назад"]
        self.current_time = new_time
        self._expire_all()
        return [f"Время: {fmt_hhmm(self.current_time)}"]

    def cmd_session(self, rest: str) -> list[str]:
        parts = rest.split()
        if not (1 <= len(parts) <= 2):
            return ["ОШИБКА: неверный формат команды session"]
        name = parts[0]
        if self._find_session(name) is not None:
            return [f"ОШИБКА: сеанс '{name}' уже существует"]

        start_time: Optional[int] = None
        if len(parts) == 2:
            start_time = parse_hhmm(parts[1])
            if start_time is None:
                return [f"ОШИБКА: некорректное время начала сеанса '{parts[1]}'"]

        self.sessions.append(Session(name=name, start_time=start_time))
        if start_time is not None:
            return [f"Сеанс {name} добавлен (начало в {fmt_hhmm(start_time)})"]
        return [f"Сеанс {name} добавлен"]

    def cmd_book(self, rest: str) -> list[str]:
        self._expire_all()
        parts = rest.split(maxsplit=2)
        if len(parts) < 3:
            return ["ОШИБКА: неверный формат команды book"]

        sess_name, seats_token, user = parts[0], parts[1], parts[2].strip()
        if not user:
            return ["ОШИБКА: пустое имя пользователя"]

        sess = self._find_session(sess_name)
        if sess is None:
            return [f"ОШИБКА: сеанс '{sess_name}' не найден"]

        if sess.start_time is not None and self.current_time >= sess.start_time:
            return [f"ОШИБКА: сеанс '{sess_name}' уже начался"]

        raw_coords = seats_token.split(",")
        if not raw_coords or any(not c for c in raw_coords):
            return ["ОШИБКА: некорректный список мест"]

        parsed_seats: list[tuple[int, int]] = []
        for rc in raw_coords:
            m = SEAT_RE.match(rc)
            if not m:
                return [f"ОШИБКА: некорректный формат места '{rc}'"]
            r = int(m.group("r"))
            s = int(m.group("s"))
            if self.hall.seat_type(r, s) is None:
                return [f"ОШИБКА: ряд {r}, место {s} не существует"]
            if (r, s) in parsed_seats:
                return [f"ОШИБКА: место {r}:{s} указано дважды"]
            if self._is_seat_taken(sess, r, s):
                return [f"ОШИБКА: ряд {r}, место {s} уже забронировано"]
            parsed_seats.append((r, s))

        out: list[str] = []
        for r, s in parsed_seats:
            b_id = len(self.all_bookings) + 1
            price = self.hall.seat_price(r, s)
            b = Booking(
                booking_id=b_id,
                session_name=sess.name,
                user=user,
                row=r,
                seat=s,
                price=price,
                created_at=self.current_time,
            )
            self.all_bookings.append(b)
            sess.bookings.append(b)
            out.append(
                f"Бронь {b_id}: {user}, сеанс {sess.name}, ряд {r}, место {s}, {price} руб. - УСПЕШНО"
            )
        return out

    def cmd_pay(self, rest: str) -> list[str]:
        self._expire_all()
        parts = rest.split(maxsplit=1)
        if len(parts) < 2 or not parts[0].isdigit():
            return ["ОШИБКА: неверный формат команды pay"]
        b_id = int(parts[0])
        user = parts[1].strip()
        if b_id <= 0 or not user:
            return ["ОШИБКА: некорректный номер брони или имя"]

        b = self._find_booking(b_id)
        if b is None:
            return [f"ОШИБКА: бронь {b_id} не найдена"]
        if b.user != user:
            return ["ОШИБКА: имя пользователя не совпадает с бронью"]
        if b.status != "active":
            return [f"ОШИБКА: бронь {b_id} нельзя оплатить (статус: {b.status})"]

        b.status = "paid"
        return [f"Бронь {b_id} оплачена"]

    def cmd_cancel(self, rest: str) -> list[str]:
        self._expire_all()
        parts = rest.split(maxsplit=1)
        if len(parts) < 2 or not parts[0].isdigit():
            return ["ОШИБКА: неверный формат команды cancel"]
        b_id = int(parts[0])
        user = parts[1].strip()
        if b_id <= 0 or not user:
            return ["ОШИБКА: некорректный номер брони или имя"]

        b = self._find_booking(b_id)
        if b is None:
            return [f"ОШИБКА: бронь {b_id} не найдена"]
        if b.user != user:
            return ["ОШИБКА: имя пользователя не совпадает с бронью"]
        if b.status not in ("active", "paid"):
            return [f"ОШИБКА: бронь {b_id} уже не активна"]

        b.status = "canceled"
        b.ended_at = self.current_time
        return [f"Бронь {b_id} отменена"]

    def cmd_free(self, rest: str) -> list[str]:
        self._expire_all()
        parts = rest.split()
        if len(parts) != 1:
            return ["ОШИБКА: неверный формат команды free"]
        sess = self._find_session(parts[0])
        if sess is None:
            return [f"ОШИБКА: сеанс '{parts[0]}' не найден"]

        taken = sum(1 for b in sess.bookings if b.is_occupying(self.current_time))
        free_cnt = self.hall.total_seats - taken
        return [f"Свободно мест: {free_cnt} из {self.hall.total_seats}"]

    def cmd_show(self, rest: str) -> list[str]:
        self._expire_all()
        parts = rest.split()
        if len(parts) != 1:
            return ["ОШИБКА: неверный формат команды show"]
        sess = self._find_session(parts[0])
        if sess is None:
            return [f"ОШИБКА: сеанс '{parts[0]}' не найден"]

        num_rows = len(self.hall.rows)
        prefix_width = len(f"Ряд {num_rows}: ")

        header_cells = "".join(f"{col:<3}" for col in range(1, self.hall.max_cols + 1))
        lines = [(" " * prefix_width + header_cells).rstrip()]

        for r_idx, row_str in enumerate(self.hall.rows, 1):
            prefix = f"Ряд {r_idx}:".ljust(prefix_width)
            cells: list[str] = []
            for s_idx, ch in enumerate(row_str, 1):
                if ch == ".":
                    sym = " "
                elif self._is_seat_taken(sess, r_idx, s_idx):
                    sym = "x"
                else:
                    sym = ch
                cells.append(f"{sym:<3}")
            lines.append((prefix + "".join(cells)).rstrip())

        return lines

    def cmd_history(self, rest: str) -> list[str]:
        self._expire_all()
        parts = rest.split()
        if len(parts) != 1:
            return ["ОШИБКА: неверный формат команды history"]
        sess = self._find_session(parts[0])
        if sess is None:
            return [f"ОШИБКА: сеанс '{parts[0]}' не найден"]

        if not sess.bookings:
            return ["История пуста"]

        lines: list[str] = []
        for b in sess.bookings:
            t_str = fmt_hhmm(b.created_at)
            if b.status == "active":
                st_str = "активно"
            elif b.status == "paid":
                st_str = "оплачено"
            elif b.status == "canceled":
                st_str = f"отменено в {fmt_hhmm(b.ended_at or 0)}"
            else:
                st_str = f"истекло в {fmt_hhmm(b.ended_at or 0)}"
            lines.append(f"  {t_str} {b.user} \u2192 ряд {b.row}, место {b.seat} ({st_str})")
        return lines

    def execute_line(self, raw_line: str) -> list[str]:
        line = raw_line.strip()
        if not line:
            return []

        parts = line.split(maxsplit=1)
        cmd = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        if cmd == "time":
            return self.cmd_time(rest)
        if cmd == "session":
            return self.cmd_session(rest)
        if cmd == "book":
            return self.cmd_book(rest)
        if cmd == "pay":
            return self.cmd_pay(rest)
        if cmd == "cancel":
            return self.cmd_cancel(rest)
        if cmd == "free":
            return self.cmd_free(rest)
        if cmd == "show":
            return self.cmd_show(rest)
        if cmd == "history":
            return self.cmd_history(rest)

        return [f"ОШИБКА: неизвестная команда '{cmd}'"]


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 1:
        print("Ошибка: укажите ровно один аргумент — файл схемы зала", file=sys.stderr)
        return 2

    hall = load_hall(args[0])
    system = CinemaSystem(hall)

    text = sys.stdin.read()
    if text.startswith("\ufeff"):
        text = text[1:]

    out: list[str] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        out.extend(system.execute_line(raw_line))

    if out:
        sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())