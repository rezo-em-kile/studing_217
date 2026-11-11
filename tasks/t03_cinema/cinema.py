import re
import sys
from dataclasses import dataclass, field
from typing import Optional

TIME_RE = re.compile(r"^(?P<h>\d{2}):(?P<m>\d{2})$")


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
classHall:
    rows: list[str]
    total_seats: int
    max_cols: int


def load_hall(path: str) -> "Hall":
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


@dataclass
class Hall:
    rows: list[str]
    total_seats: int
    max_cols: int


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 1:
        print("Ошибка: укажите ровно один аргумент — файл схемы зала", file=sys.stderr)
        return 2
    load_hall(args[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())