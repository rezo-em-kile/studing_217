import math
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

NUM_RE = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

FUNCTIONS = {"sqrt", "ln", "log", "abs", "sin", "cos", "tan", "exp"}
CONSTANTS = {"pi": math.pi, "e": math.e}

MAX_INT_ABS = 10 ** 1000


class MathError(Exception):
    pass


def _is_int_val(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool)


def _check_number_bounds(val: Any) -> Any:
    if _is_int_val(val):
        if abs(val) >= MAX_INT_ABS:
            raise MathError("слишком большое целое число")
        return val
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            raise MathError("числовое переполнение или неопределённость")
        return val
    raise MathError("ожидалось число")


def parse_number_literal(raw: str) -> int | float:
    if not NUM_RE.match(raw):
        raise MathError(f"некорректное число '{raw}'")
    if "." not in raw and "e" not in raw and "E" not in raw:
        val = int(raw)
        if abs(val) >= MAX_INT_ABS:
            raise MathError("слишком большое целое число")
        return val
    val_f = float(raw)
    if math.isnan(val_f) or math.isinf(val_f):
        raise MathError("числовое переполнение")
    return val_f


def format_number(val: int | float, precision: int = 10, force_plain: bool = False) -> str:
    if _is_int_val(val):
        return str(val)

    x = float(val)
    if math.isnan(x) or math.isinf(x):
        raise MathError("некорректное число для вывода")

    if x == 0.0:
        return "0.0"

    abs_x = abs(x)
    use_sci = (not force_plain) and (abs_x >= 1e15 or abs_x < 1e-6)

    if use_sci:
        d = Decimal(str(x))
        sign = "-" if d < 0 else ""
        d_abs = abs(d)
        exp = d_abs.adjusted()
        mantissa = d_abs.scaleb(-exp)
        q = Decimal("1") if precision == 0 else Decimal("1e-" + str(precision))
        mantissa_rounded = mantissa.quantize(q, rounding=ROUND_HALF_UP)
        if mantissa_rounded >= Decimal("10"):
            mantissa_rounded /= Decimal("10")
            exp += 1
        m_str = format(mantissa_rounded, "f")
        if "." in m_str:
            m_str = m_str.rstrip("0").rstrip(".")
        exp_sign = "+" if exp >= 0 else "-"
        return f"{sign}{m_str}e{exp_sign}{abs(exp)}"

    d = Decimal(str(x))
    q = Decimal("1") if precision == 0 else Decimal("1e-" + str(precision))
    rounded = d.quantize(q, rounding=ROUND_HALF_UP)
    if rounded == 0:
        return "0.0"

    s = format(rounded, "f")
    if "." in s:
        int_part, frac_part = s.split(".", 1)
        frac_part = frac_part.rstrip("0")
        if not frac_part:
            frac_part = "0"
        return f"{int_part}.{frac_part}"
    return f"{s}.0"


def _tokenize_math(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue

        if ch in "+-*/(),":
            if ch == "*" and i + 1 < n and expr[i + 1] == "*":
                tokens.append(("OP", "^"))
                i += 2
            elif ch in "+-*/":
                tokens.append(("OP", ch))
                i += 1
            elif ch == "(":
                tokens.append(("LPAREN", "("))
                i += 1
            elif ch == ")":
                tokens.append(("RPAREN", ")"))
                i += 1
            elif ch == ",":
                tokens.append(("COMMA", ","))
                i += 1
            continue

        if ch == "^":
            tokens.append(("OP", "^"))
            i += 1
            continue

        if ("0" <= ch <= "9") or (ch == "." and i + 1 < n and "0" <= expr[i + 1] <= "9"):
            start = i
            while i < n and "0" <= expr[i] <= "9":
                i += 1
            if i < n and expr[i] == ".":
                i += 1
                while i < n and "0" <= expr[i] <= "9":
                    i += 1
            if i < n and expr[i] in "eE":
                i += 1
                if i < n and expr[i] in "+-":
                    i += 1
                exp_start = i
                while i < n and "0" <= expr[i] <= "9":
                    i += 1
                if exp_start == i:
                    raise MathError(f"некорректная экспонента в числе '{expr[start:i]}'")
            if i < n and (expr[i].isalpha() or expr[i] in "_."):
                raise MathError(f"некорректный числовой литерал '{expr[start:i+1]}'")
            tokens.append(("NUM", expr[start:i]))
            continue

        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ch == "_":
            start = i
            while i < n and (("a" <= expr[i] <= "z") or ("A" <= expr[i] <= "Z") or ("0" <= expr[i] <= "9") or expr[i] == "_"):
                i += 1
            tokens.append(("IDENT", expr[start:i]))
            continue

        raise MathError(f"недопустимый символ '{ch}'")

    return tokens


def _apply_pow(base: int | float, exp: int | float) -> int | float:
    if _is_int_val(base) and _is_int_val(exp):
        if exp < 0:
            if base == 0:
                raise MathError("деление на ноль при возведении в отрицательную степень")
            res = float(base) ** exp
            return _check_number_bounds(res)
        if exp == 0:
            if base == 0:
                raise MathError("неопределённость 0^0")
            return 1
        if abs(base) > 1 and exp > 4000:
            raise MathError("слишком большая степень")
        res_i = base ** exp
        return _check_number_bounds(res_i)

    b_f = float(base)
    e_f = float(exp)
    if b_f == 0.0 and e_f <= 0.0:
        raise MathError("недопустимое возведение нуля в степень <= 0")
    if b_f < 0.0 and not e_f.is_integer():
        raise MathError("возведение отрицательного числа в дробную степень")
    try:
        res_f = math.pow(b_f, e_f)
    except (ValueError, OverflowError):
        raise MathError("ошибка при возведении в степень")
    return _check_number_bounds(res_f)


def _apply_func(name: str, args: list[int | float]) -> int | float:
    if name == "sqrt":
        if len(args) != 1:
            raise MathError("sqrt принимает ровно 1 аргумент")
        x = float(args[0])
        if x < 0:
            raise MathError("корень из отрицательного числа")
        return _check_number_bounds(math.sqrt(x))

    if name == "ln":
        if len(args) != 1:
            raise MathError("ln принимает ровно 1 аргумент")
        x = float(args[0])
        if x <= 0:
            raise MathError("логарифм определён только для положительных чисел")
        return _check_number_bounds(math.log(x))

    if name == "log":
        if len(args) == 1:
            x = float(args[0])
            if x <= 0:
                raise MathError("логарифм определён только для положительных чисел")
            return _check_number_bounds(math.log10(x))
        if len(args) == 2:
            x = float(args[0])
            base = float(args[1])
            if x <= 0:
                raise MathError("логарифм определён только для положительных чисел")
            if base <= 0 or base == 1.0:
                raise MathError("некорректное основание логарифма")
            return _check_number_bounds(math.log(x, base))
        raise MathError("log принимает 1 или 2 аргумента")

    if name == "abs":
        if len(args) != 1:
            raise MathError("abs принимает ровно 1 аргумент")
        val = args[0]
        return _check_number_bounds(-val if val < 0 else val)

    if name == "sin":
        if len(args) != 1:
            raise MathError("sin принимает ровно 1 аргумент")
        res = math.sin(float(args[0]))
        return 0.0 if abs(res) < 1e-12 else _check_number_bounds(res)

    if name == "cos":
        if len(args) != 1:
            raise MathError("cos принимает ровно 1 аргумент")
        res = math.cos(float(args[0]))
        return 0.0 if abs(res) < 1e-12 else _check_number_bounds(res)

    if name == "tan":
        if len(args) != 1:
            raise MathError("tan принимает ровно 1 аргумент")
        x = float(args[0])
        if abs(math.cos(x)) < 1e-12:
            raise MathError("тангенс не определён (деление на ноль)")
        res = math.tan(x)
        return 0.0 if abs(res) < 1e-12 else _check_number_bounds(res)

    if name == "exp":
        if len(args) != 1:
            raise MathError("exp принимает ровно 1 аргумент")
        try:
            res = math.exp(float(args[0]))
        except OverflowError:
            raise MathError("переполнение в функции exp")
        return _check_number_bounds(res)

    raise MathError(f"неизвестная функция '{name}'")


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]], variables: dict[str, int | float]):
        self.tokens = tokens
        self.pos = 0
        self.vars = variables

    def peek(self) -> Optional[tuple[str, str]]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self) -> tuple[str, str]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> int | float:
        if not self.tokens:
            raise MathError("пустое выражение")
        val = self.parse_add()
        if self.peek() is not None:
            raise MathError(f"неожиданный токен '{self.peek()[1]}'")
        return val

    def parse_add(self) -> int | float:
        left = self.parse_mul()
        while True:
            tok = self.peek()
            if tok and tok[0] == "OP" and tok[1] in ("+", "-"):
                op = self.consume()[1]
                right = self.parse_mul()
                if _is_int_val(left) and _is_int_val(right):
                    left = _check_number_bounds(left + right if op == "+" else left - right)
                else:
                    try:
                        res = float(left) + float(right) if op == "+" else float(left) - float(right)
                    except OverflowError:
                        raise MathError("числовое переполнение")
                    left = _check_number_bounds(res)
            else:
                break
        return left

    def parse_mul(self) -> int | float:
        left = self.parse_unary()
        while True:
            tok = self.peek()
            if tok and tok[0] == "OP" and tok[1] in ("*", "/"):
                op = self.consume()[1]
                right = self.parse_unary()
                if op == "*":
                    if _is_int_val(left) and _is_int_val(right):
                        left = _check_number_bounds(left * right)
                    else:
                        try:
                            res = float(left) * float(right)
                        except OverflowError:
                            raise MathError("числовое переполнение")
                        left = _check_number_bounds(res)
                else:
                    if right == 0:
                        raise MathError("деление на ноль")
                    try:
                        res = float(left) / float(right)
                    except OverflowError:
                        raise MathError("числовое переполнение")
                    left = _check_number_bounds(res)
            else:
                break
        return left

    def parse_unary(self) -> int | float:
        tok = self.peek()
        if tok and tok[0] == "OP" and tok[1] in ("+", "-"):
            op = self.consume()[1]
            val = self.parse_unary()
            if op == "-":
                return _check_number_bounds(-val)
            return val
        return self.parse_power()

    def parse_power(self) -> int | float:
        base = self.parse_primary()
        tok = self.peek()
        if tok and tok[0] == "OP" and tok[1] == "^":
            self.consume()
            exp = self.parse_unary()
            return _apply_pow(base, exp)
        return base

    def parse_primary(self) -> int | float:
        tok = self.peek()
        if tok is None:
            raise MathError("неожиданный конец выражения")

        kind, text = tok
        if kind == "NUM":
            self.consume()
            return parse_number_literal(text)

        if kind == "LPAREN":
            self.consume()
            val = self.parse_add()
            nxt = self.peek()
            if nxt is None or nxt[0] != "RPAREN":
                raise MathError("не закрыта скобка ')'")
            self.consume()
            return val

        if kind == "IDENT":
            self.consume()
            nxt = self.peek()
            if nxt and nxt[0] == "LPAREN":
                if text not in FUNCTIONS:
                    raise MathError(f"неизвестная функция '{text}'")
                self.consume()  # '('
                args: list[int | float] = []
                if self.peek() and self.peek()[0] == "RPAREN":
                    self.consume()
                else:
                    while True:
                        args.append(self.parse_add())
                        sep = self.peek()
                        if sep and sep[0] == "COMMA":
                            self.consume()
                            continue
                        if sep and sep[0] == "RPAREN":
                            self.consume()
                            break
                        raise MathError("ожидалась ',' или ')' в аргументах функции")
                return _apply_func(text, args)

            if text in self.vars:
                return _check_number_bounds(self.vars[text])
            if text in CONSTANTS:
                return CONSTANTS[text]
            if text in FUNCTIONS:
                raise MathError(f"функция '{text}' вызвана без скобок")
            raise MathError(f"неизвестная переменная '{text}'")

        raise MathError(f"неожиданный элемент '{text}'")


def parse_where_clause(raw_where: str) -> dict[str, int | float | bool]:
    parts = [p.strip() for p in raw_where.split(",")]
    if not parts or any(not p for p in parts):
        raise MathError("некорректный блок 'где'")

    result: dict[str, int | float | bool] = {}
    for part in parts:
        if "=" not in part:
            raise MathError(f"ожидалось 'переменная=значение', получено '{part}'")
        k_raw, v_raw = part.split("=", 1)
        name = k_raw.strip()
        val_str = v_raw.strip()
        if not IDENT_RE.match(name):
            raise MathError(f"некорректное имя переменной '{name}'")
        if name.lower() in ("true", "false", "and", "or", "not"):
            raise MathError(f"недопустимое имя переменной '{name}'")
        if not val_str:
            raise MathError(f"не указано значение для переменной '{name}'")

        low = val_str.lower()
        if low == "true":
            result[name] = True
        elif low == "false":
            result[name] = False
        else:
            sign = 1
            num_part = val_str
            if num_part.startswith("-"):
                sign = -1
                num_part = num_part[1:].strip()
            elif num_part.startswith("+"):
                num_part = num_part[1:].strip()
            num = parse_number_literal(num_part)
            result[name] = -num if sign == -1 else num

    return result


def evaluate_math(expr: str, variables: Optional[dict[str, Any]] = None) -> int | float:
    num_vars: dict[str, int | float] = {}
    if variables:
        for k, v in variables.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise MathError(f"переменная '{k}' должна быть числом")
            num_vars[k] = v

    tokens = _tokenize_math(expr)
    parser = _Parser(tokens, num_vars)
    return parser.parse()