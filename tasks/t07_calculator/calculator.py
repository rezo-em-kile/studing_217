# Version: 1.0.1
import re
import sys

from calc_convert import ConvertError, convert_command
from calc_logic import LogicError, evaluate_logic, has_logic_construct
from calc_math import MathError, evaluate_math, format_number, parse_where_clause
from calc_matrix import MatrixError, evaluate_matrix_command

WHERE_SPLIT_RE = re.compile(r",\s*где\s+", re.IGNORECASE)


def plural_digits(n: int) -> str:
    rem100 = n % 100
    rem10 = n % 10
    if 11 <= rem100 <= 14:
        return "знаков"
    if rem10 == 1:
        return "знак"
    if rem10 in (2, 3, 4):
        return "знака"
    return "знаков"


class CalculatorApp:
    def __init__(self) -> None:
        self.precision: int = 10
        self.history: list[str] = []

    def handle_line(self, raw_line: str) -> tuple[str, bool]:
        """Возвращает (строка_ответа, является_ли_ошибкой)."""
        line = raw_line.strip()
        low = line.lower()

        # Команда help
        if low == "help":
            help_text = "\n".join([
                "Команды:",
                "  <выражение> [, где x=1, ...]   - арифметика и функции",
                "  <логика> [, где x=true, ...]   - логические выражения (AND, OR, NOT)",
                "  convert <N> <из> to|in <в>     - конвертер единиц (длина, масса, время, температура)",
                "  matrix <операция>              - матричные операции (+, -, *, det, transpose/t)",
                "  precision [0..15]              - показать или установить точность вывода",
                "  history                        - показать историю вычислений",
                "  save <файл>                    - сохранить историю в файл",
                "  help                           - эта справка",
                "  exit / quit                    - выход",
            ])
            return help_text, False

        # Команда history
        if low == "history":
            if not self.history:
                return "История пуста", False
            return "\n".join(f"  {idx}. {item}" for idx, item in enumerate(self.history, 1)), False

        # Команда save
        if low == "save" or low.startswith("save ") or low.startswith("save\t"):
            parts = line.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                return "ОШИБКА: не указано имя файла для сохранения", True
            path = parts[1].strip()
            try:
                with open(path, "w", encoding="utf-8") as f:
                    for idx, item in enumerate(self.history, 1):
                        f.write(f"{idx}. {item}\n")
            except OSError as e:
                return f"ОШИБКА: не удалось сохранить историю в '{path}': {e}", True
            return f"История сохранена: {path}", False

        # Команда precision
        if low == "precision" or low.startswith("precision ") or low.startswith("precision\t"):
            parts = line.split()
            if len(parts) == 1:
                return (
                    f"Текущая точность: {self.precision} {plural_digits(self.precision)} после запятой",
                    False,
                )
            if len(parts) != 2:
                return "ОШИБКА: команда precision принимает одно целое число от 0 до 15", True
            raw_p = parts[1]
            if not raw_p.isdigit():
                return f"ОШИБКА: некорректная точность '{raw_p}' (допустимо целое 0..15)", True
            val_p = int(raw_p)
            if not (0 <= val_p <= 15):
                return f"ОШИБКА: точность должна быть от 0 до 15, получено {val_p}", True
            self.precision = val_p
            return (
                f"Точность установлена: {self.precision} {plural_digits(self.precision)} после запятой",
                False,
            )

        # Команда convert
        if low == "convert" or low.startswith("convert ") or low.startswith("convert\t"):
            try:
                ans = convert_command(line)
                val_part = ans[2:] if ans.startswith("= ") else ans
                self.history.append(f"{line} = {val_part}")
                return ans, False
            except ConvertError as e:
                self.history.append(f"{line} → ОШИБКА")
                return f"ОШИБКА: {e}", True

        # Команда matrix
        if low == "matrix" or low.startswith("matrix ") or low.startswith("matrix\t"):
            rest = line[6:].strip()
            try:
                multiline_ans, singleline_ans = evaluate_matrix_command(rest, self.precision)
                self.history.append(f"{line} = {singleline_ans}")
                return multiline_ans, False
            except MatrixError as e:
                self.history.append(f"{line} → ОШИБКА")
                return f"ОШИБКА: {e}", True

        # Вычисления (арифметика или логика, опционально с ", где ...")
        try:
            where_matches = list(WHERE_SPLIT_RE.finditer(line))
            if len(where_matches) > 1:
                raise MathError("блок 'где' должен встречаться не более одного раза")

            if where_matches:
                m = where_matches[0]
                expr_part = line[:m.start()].strip()
                where_part = line[m.end():].strip()
                variables = parse_where_clause(where_part)
            else:
                if re.search(r"(?:^|\s)где(?:\s|$)", line, re.IGNORECASE):
                    raise MathError("некорректный синтаксис блока 'где'")
                expr_part = line
                variables = {}

            if not expr_part:
                raise MathError("пустое выражение")

            if has_logic_construct(expr_part):
                res_bool = evaluate_logic(expr_part, variables)
                res_str = "true" if res_bool else "false"
                self.history.append(f"{line} = {res_str}")
                return f"= {res_str}", False

            res_num = evaluate_math(expr_part, variables)
            formatted_num = format_number(res_num, self.precision)
            self.history.append(f"{line} = {formatted_num}")
            return f"= {formatted_num}", False

        except (MathError, LogicError) as e:
            self.history.append(f"{line} → ОШИБКА")
            return f"ОШИБКА: {e}", True


def main() -> int:
    app = CalculatorApp()
    args = sys.argv[1:]

    if args:
        query = " ".join(args)
        if not query.strip():
            return 0
        output, is_err = app.handle_line(query)
        print(output)
        return 1 if is_err else 0

    for raw_line in sys.stdin:
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.lower() in ("exit", "quit"):
            break
        output, _ = app.handle_line(stripped)
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())