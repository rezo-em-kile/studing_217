"""Выражения и числа: разбор и вычисление арифметических выражений, вывод чисел.

Целые считаются точно (int Python), деление «/» всегда даёт дробное число.
eval/exec не используются: выражение разбирается рекурсивным спуском.

Грамматика (от слабого к сильному):
    expr    := term (('+' | '-') term)*
    term    := unary (('*' | '/') unary)*
    unary   := ('+' | '-') unary | power
    power   := primary (('^' | '**') unary)?      - правоассоциативно, 2^-1, -2^2 = -4
    primary := ЧИСЛО | ИМЯ | ИМЯ '(' expr (',' expr)* ')' | '(' expr ')'
"""
import math
import re
from decimal import ROUND_HALF_UP, Decimal, localcontext

INT_LIMIT = 10 ** 1000
DEFAULT_PRECISION = 10
MAX_PRECISION = 15
TRIG_ZERO = 1e-12

NUMBER_PATTERN = r"(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
NUMBER_RE = re.compile(NUMBER_PATTERN)
SIGNED_NUMBER_RE = re.compile(r"[+-]?" + NUMBER_PATTERN)
NAME_RE = re.compile(r"[^\W\d]\w*")
IDENTIFIER_RE = re.compile(r"^[^\W\d]\w*$")
CONSTANTS = (("pi", math.pi), ("e", math.e))


class MathError(Exception):
    """Ошибка в выражении или при вычислении."""


# --- числа ---

def parse_number(text):
    """Число из записи «12», «3.5», «.5», «5.», «1e3» (со знаком). int для целых без точки и порядка."""
    text = text.strip()
    if not SIGNED_NUMBER_RE.fullmatch(text):
        raise MathError(f"«{text}» - не число")
    if re.fullmatch(r"[+-]?[0-9]+", text):
        value = int(text)
        check_int(value)
        return value
    value = float(text)
    if not math.isfinite(value):
        raise MathError(f"число «{text}» слишком большое")
    return value


def check_int(value):
    if abs(value) >= INT_LIMIT:
        raise MathError("целое число слишком большое (должно быть меньше 10^1000 по модулю)")
    return value


def check_float(value):
    if isinstance(value, complex) or not math.isfinite(value):
        raise MathError("результат не является конечным действительным числом")
    return value


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _round_half_up(value, precision):
    with localcontext() as context:
        context.prec = 2000
        return Decimal(repr(value)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)


def _fixed(value, precision):
    """Дробное число в обычной записи: округление «как в школе», лишние нули убраны, но не последний."""
    rounded = _round_half_up(value, precision)
    if rounded == 0:
        return "0.0"
    text = format(rounded, "f")
    if "." not in text:
        return text + ".0"
    text = text.rstrip("0")
    return text + "0" if text.endswith(".") else text


def _scientific(value, precision):
    with localcontext() as context:
        context.rounding = ROUND_HALF_UP
        context.prec = 2000
        text = format(Decimal(repr(value)), f".{precision}e")
    mantissa, exponent = text.split("e")
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    sign = "-" if exponent.startswith("-") else "+"
    return f"{mantissa}e{sign}{int(exponent.lstrip('+-'))}"


def format_number(value, precision=DEFAULT_PRECISION, plain=False):
    """Число калькулятора: целое - все цифры; дробное - precision знаков после запятой.

    plain=True - всегда обычная запись (элементы матриц), иначе при |x| ≥ 1e15
    или 0 < |x| < 1e-6 - экспоненциальная.
    """
    if isinstance(value, bool) or not is_number(value):
        raise MathError("ожидалось число")
    if isinstance(value, int):
        return str(value)
    if value == 0:
        return "0.0"
    if not plain and (abs(value) >= 1e15 or abs(value) < 1e-6):
        return _scientific(value, precision)
    return _fixed(value, precision)


# --- разбор выражения ---

TOKEN_RE = re.compile(r"\s*(?:(?P<number>" + NUMBER_PATTERN + r")|(?P<name>[^\W\d]\w*)|(?P<op>\*\*|[-+*/^(),]))")


def tokenize(text):
    tokens = []
    position = 0
    text = text.rstrip()
    while position < len(text):
        match = TOKEN_RE.match(text, position)
        if not match:
            char = text[position:].lstrip()[:1]
            raise MathError(f"недопустимый символ «{char}»")
        position = match.end()
        if match.group("number"):
            tokens.append(("number", match.group("number")))
        elif match.group("name"):
            tokens.append(("name", match.group("name")))
        else:
            op = match.group("op")
            tokens.append(("op", "^" if op == "**" else op))
    return tokens


FUNCTIONS = ("sqrt", "ln", "log", "abs", "sin", "cos", "tan", "exp", "asin", "acos", "atan")


class Parser:
    def __init__(self, text, variables):
        self.tokens = tokenize(text)
        self.position = 0
        self.variables = variables

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else (None, None)

    def take(self):
        token = self.peek()
        self.position += 1
        return token

    def expect(self, op):
        kind, value = self.take()
        if kind != "op" or value != op:
            raise MathError(f"ожидалось «{op}»" + (f", а встретилось «{value}»" if value else " в конце"))

    def parse(self):
        if not self.tokens:
            raise MathError("пустое выражение")
        value = self.expr()
        if self.position != len(self.tokens):
            raise MathError(f"лишнее «{self.peek()[1]}» в выражении")
        return value

    def expr(self):
        value = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            value = add(value, self.term(), op)
        return value

    def term(self):
        value = self.unary()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.take()[1]
            right = self.unary()
            value = multiply(value, right) if op == "*" else divide(value, right)
        return value

    def unary(self):
        if self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            value = self.unary()
            return negate(value) if op == "-" else value
        return self.power()

    def power(self):
        base = self.primary()
        if self.peek() == ("op", "^"):
            self.take()
            return power(base, self.unary())
        return base

    def primary(self):
        kind, value = self.take()
        if kind == "number":
            return parse_number(value)
        if kind == "op" and value == "(":
            result = self.expr()
            self.expect(")")
            return result
        if kind == "name":
            if self.peek() == ("op", "("):
                self.take()
                args = [self.expr()]
                while self.peek() == ("op", ","):
                    self.take()
                    args.append(self.expr())
                self.expect(")")
                return call(value, args)
            return self.lookup(value)
        if kind is None:
            raise MathError("выражение оборвалось: не хватает числа")
        raise MathError(f"неожиданное «{value}»")

    def lookup(self, name):
        for key, value in self.variables:
            if key == name:
                if not is_number(value):
                    raise MathError(f"переменная {name} не числовая")
                return value
        for key, value in CONSTANTS:
            if key == name:
                return value
        if name in FUNCTIONS:
            raise MathError(f"после функции {name} нужны скобки: {name}(…)")
        raise MathError(f"неизвестная переменная {name} (значения задаются после «где»)")


# --- операции ---

def result(value):
    return check_int(value) if isinstance(value, int) else check_float(value)


def add(left, right, op):
    try:
        return result(left + right if op == "+" else left - right)
    except OverflowError:
        raise MathError("число слишком большое") from None


def multiply(left, right):
    try:
        return result(left * right)
    except OverflowError:
        raise MathError("число слишком большое") from None


def divide(left, right):
    if right == 0:
        raise MathError("деление на ноль")
    try:
        return check_float(float(left / right))
    except OverflowError:
        raise MathError("число слишком большое") from None


def negate(value):
    return -value if isinstance(value, int) else check_float(-value) + 0.0


def power(base, exponent):
    if base == 0 and exponent == 0:
        raise MathError("0 в степени 0 не определён")
    if base == 0 and exponent < 0:
        raise MathError("деление на ноль: 0 в отрицательной степени")
    if isinstance(base, int) and isinstance(exponent, int) and exponent >= 0:
        if abs(base) > 1 and exponent * math.log10(abs(base)) > 1001:
            raise MathError("целое число слишком большое (должно быть меньше 10^1000 по модулю)")
        return check_int(base ** exponent)
    if base < 0 and not float(exponent).is_integer():
        raise MathError("отрицательное число нельзя возводить в дробную степень")
    try:
        return check_float(float(base) ** float(exponent))
    except OverflowError:
        raise MathError("число слишком большое") from None
    except ZeroDivisionError:
        raise MathError("деление на ноль") from None


def call(name, args):
    if name not in FUNCTIONS:
        raise MathError(f"неизвестная функция {name}")
    expected = "1 или 2 аргумента" if name == "log" else "1 аргумент"
    if len(args) != 1 and not (name == "log" and len(args) == 2):
        raise MathError(f"у функции {name} {expected}, передано {len(args)}")
    try:
        x = args[0]
        if name == "abs":
            return abs(x) if isinstance(x, int) else check_float(abs(x))
        x = float(x)
        if name == "sqrt":
            if x < 0:
                raise MathError("квадратный корень из отрицательного числа")
            return check_float(math.sqrt(x))
        if name in ("ln", "log"):
            if x <= 0:
                raise MathError("логарифм определён только для положительных чисел")
            if name == "ln":
                return check_float(math.log(x))
            if len(args) == 1:
                return check_float(math.log10(x))
            base = float(args[1])
            if base <= 0 or base == 1:
                raise MathError("основание логарифма должно быть положительным и не равным 1")
            return check_float(math.log(x) / math.log(base))
        if name in ("asin", "acos"):
            # доработка по просьбе заказчика: обратные тригонометрические функции (в работе)
            if not -1 <= x <= 1:
                raise MathError(f"{name} определён только для чисел от -1 до 1")
            return check_float(math.asin(x) if name == "asin" else math.acos(x))
        if name == "atan":
            return check_float(math.atan(x))
        if name == "exp":
            return check_float(math.exp(x))
        if name == "tan" and abs(math.cos(x)) < TRIG_ZERO:
            raise MathError("тангенс не определён (cos = 0)")
        value = {"sin": math.sin, "cos": math.cos, "tan": math.tan}[name](x)
        return 0.0 if abs(value) < TRIG_ZERO else check_float(value)
    except OverflowError:
        raise MathError(f"{name}: число слишком большое") from None


# --- переменные ---

def parse_assignments(text):
    """«x=5, y=true» -> [(имя, значение)]; значение - число или True/False."""
    result_list = []
    for part in text.split(","):
        name, sign, value_text = part.partition("=")
        name, value_text = name.strip(), value_text.strip()
        if not sign or not name or not value_text:
            raise MathError(f"после «где» нужно «имя=значение», получено «{part.strip()}»")
        if not IDENTIFIER_RE.match(name):
            raise MathError(f"«{name}» - неверное имя переменной")
        if any(key == name for key, _ in result_list):
            raise MathError(f"переменная {name} задана дважды")
        if value_text.lower() in ("true", "false"):
            value = value_text.lower() == "true"
        else:
            value = parse_number(value_text)
        result_list.append((name, value))
    return result_list


def evaluate(text, variables=()):
    """Значение арифметического выражения (int или float)."""
    return Parser(text, list(variables)).parse()
