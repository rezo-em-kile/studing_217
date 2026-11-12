"""Калькулятор в командной строке.

    python calculator.py            - строки со стандартного ввода до конца или до exit/quit
    python calculator.py "2 + 2"    - одна строка из аргументов (код 1, если ответ - ошибка)

Связывает модули calc_math (выражения и числа), calc_convert (конвертер),
calc_matrix (матрицы) и calc_logic (логика); сами модули друг друга не импортируют.
"""
import re
import sys

import calc_convert
import calc_logic
import calc_math
import calc_matrix

WHERE_RE = re.compile(r"\s*,?\s*(?<!\w)где(?!\w)\s*", re.IGNORECASE)
HELP = """Команды:
  выражение                  2 + 2 * 2, sqrt(16) + 3^2, log(8, 2), sin(pi / 2)
  выражение, где x=…, y=…    значения переменных: x * 2, где x=5
  логическое выражение       true AND x > 5, где x=7  (AND, OR, NOT, < <= > >= == !=)
  convert 5 km to miles      конвертер: длина, масса, время, температура
  matrix A + B, A - B, A * B, A * 3, det A, transpose A (t A)
                             матрицы в виде [[1, 2], [3, 4]]
  precision [N]              точность (знаков после запятой, 0-15)
  history                    история вычислений
  save ФАЙЛ                  сохранить историю в файл
  help                       эта справка
  exit, quit                 выход"""

ERRORS = (calc_math.MathError, calc_convert.ConvertError, calc_matrix.MatrixError, calc_logic.LogicError,
          ArithmeticError, ValueError)


class Calculator:
    def __init__(self):
        self.precision = calc_math.DEFAULT_PRECISION
        self.history = []

    def number(self, value):
        return calc_math.format_number(value, self.precision)

    def element(self, value):
        return calc_math.format_number(value, self.precision, plain=True)

    # --- вычисления (попадают в историю) ---

    def calculate(self, line):
        """Ответ на вычисление: (строки ответа, текст для истории)."""
        word, _, rest = line.partition(" ")
        command = word.lower()
        if command == "convert":
            text = calc_convert.run(rest)
            return [f"= {text}"], text
        if command == "matrix":
            value = calc_matrix.evaluate(rest)
            if not isinstance(value, list):
                text = self.number(value)
                return [f"= {text}"], text
            return ([f"= {calc_matrix.format_matrix(value, self.element)}"],
                    calc_matrix.format_matrix(value, self.element, one_line=True))
        parts = WHERE_RE.split(line, maxsplit=1)
        expression = parts[0].strip()
        variables = calc_math.parse_assignments(parts[1]) if len(parts) > 1 else []
        if not expression:
            raise calc_math.MathError("нет выражения перед «где»")
        if calc_logic.looks_logical(expression):
            value = calc_logic.evaluate(expression, variables,
                                        lambda text: calc_math.evaluate(text, variables))
            text = calc_logic.format_bool(value)
        else:
            text = self.number(calc_math.evaluate(expression, variables))
        return [f"= {text}"], text

    # --- служебные команды ---

    def set_precision(self, args):
        if not args:
            return [f"Текущая точность: {self.precision} {digits_word(self.precision)} после запятой"]
        if len(args) != 1 or not re.fullmatch(r"[0-9]+", args[0]) or int(args[0]) > calc_math.MAX_PRECISION:
            raise calc_math.MathError(f"точность - целое число от 0 до {calc_math.MAX_PRECISION}")
        self.precision = int(args[0])
        return [f"Точность установлена: {self.precision} {digits_word(self.precision)} после запятой"]

    def history_lines(self, indent):
        lines = []
        for number, (line, text) in enumerate(self.history, 1):
            lines.append(f"{indent}{number}. {line} = {text}" if text is not None else f"{indent}{number}. {line} → ОШИБКА")
        return lines

    def save(self, name):
        if not name:
            raise calc_math.MathError("укажите файл: save ФАЙЛ")
        try:
            with open(name, "w", encoding="utf-8") as file:
                for line in self.history_lines(""):
                    file.write(line + "\n")
        except OSError as error:
            raise calc_math.MathError(f"не удалось сохранить историю в {name}: {error.strerror}") from None
        return [f"История сохранена: {name}"]

    def handle(self, line):
        """Ответ на строку и признак ошибки."""
        word, _, rest = line.partition(" ")
        command = word.lower()
        try:
            if command == "precision":
                return self.set_precision(rest.split()), False
            if command == "history" and not rest.strip():
                return self.history_lines("  ") or ["История пуста"], False
            if command == "help" and not rest.strip():
                return HELP.splitlines(), False
            if command == "save":
                return self.save(rest.strip()), False
        except ERRORS as error:
            return [f"ОШИБКА: {error}"], True
        try:
            answer, text = self.calculate(line)
        except ERRORS as error:
            self.history.append((line, None))
            return [f"ОШИБКА: {error}"], True
        self.history.append((line, text))
        return answer, False


def digits_word(count):
    if count % 10 == 1 and count % 100 != 11:
        return "знак"
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "знака"
    return "знаков"


def use_utf8_streams():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main():
    use_utf8_streams()
    calculator = Calculator()
    if len(sys.argv) > 1:
        answer, failed = calculator.handle(" ".join(sys.argv[1:]).strip())
        for text in answer:
            print(text)
        sys.exit(1 if failed else 0)
    first = True
    for raw in sys.stdin:
        line = (raw.lstrip("﻿") if first else raw).strip()
        first = False
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break
        answer, _ = calculator.handle(line)
        for text in answer:
            print(text, flush=True)


if __name__ == "__main__":
    main()
