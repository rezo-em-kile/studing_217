"""Матричный калькулятор: A + B, A - B, A * B, A * число, число * A, det A, transpose A (t A).

Матрица записывается как [[1, 2], [3, 4]]; элементы - целые или дробные числа со знаком.
Целые остаются целыми, определитель считается точно (через дроби Fraction).
"""
import math
import re
from fractions import Fraction

NUMBER_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
TOKEN_RE = re.compile(r"\s*(?:(?P<number>[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
                      r"|(?P<punct>[\[\],])|(?P<op>[-+*])|(?P<word>[^\W\d]\w*))")


class MatrixError(Exception):
    """Ошибка в матричной команде."""


def parse_number(text):
    if re.fullmatch(r"[+-]?[0-9]+", text):
        return int(text)
    value = float(text)
    if not math.isfinite(value):
        raise MatrixError(f"число «{text}» слишком большое")
    return value


def tokenize(text):
    tokens = []
    position = 0
    text = text.rstrip()
    while position < len(text):
        match = TOKEN_RE.match(text, position)
        if not match:
            raise MatrixError(f"недопустимый символ «{text[position:].strip()[:1]}»")
        kind = match.lastgroup
        tokens.append((kind, match.group(kind)))
        position = match.end()
    return tokens


def size(matrix):
    return f"{len(matrix)}×{len(matrix[0])}"


class Parser:
    def __init__(self, text):
        self.tokens = tokenize(text)
        self.position = 0

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else (None, None)

    def take(self):
        token = self.peek()
        self.position += 1
        return token

    def expect(self, value):
        kind, got = self.take()
        if got != value:
            raise MatrixError(f"в записи матрицы ожидалось «{value}»" + (f", а встретилось «{got}»" if got else ""))

    def operand(self):
        kind, value = self.peek()
        if kind == "number":
            self.take()
            return parse_number(value)
        if value == "[":
            return self.matrix()
        if kind is None:
            raise MatrixError("не хватает матрицы")
        raise MatrixError(f"«{value}» - не матрица и не число")

    def matrix(self):
        self.expect("[")
        rows = [self.row()]
        while self.peek()[1] == ",":
            self.take()
            rows.append(self.row())
        self.expect("]")
        if any(len(row) != len(rows[0]) for row in rows):
            raise MatrixError("строки матрицы разной длины")
        return rows

    def row(self):
        if self.peek()[1] != "[":
            raise MatrixError("матрица - это список строк: [[1, 2], [3, 4]]")
        self.take()
        values = []
        while True:
            kind, value = self.take()
            if kind != "number":
                raise MatrixError(f"элемент матрицы должен быть числом, а не «{value or 'пусто'}»")
            values.append(parse_number(value))
            kind, value = self.take()
            if value == "]":
                return values
            if value != ",":
                raise MatrixError("элементы строки матрицы разделяются запятой")

    def done(self):
        return self.position == len(self.tokens)


def is_matrix(value):
    return isinstance(value, list)


def add(a, b, sign):
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        raise MatrixError(f"несовместимые размеры матриц ({size(a)} и {size(b)})")
    return [[x + sign * y for x, y in zip(row_a, row_b)] for row_a, row_b in zip(a, b)]


def multiply(a, b):
    if len(a[0]) != len(b):
        raise MatrixError(f"несовместимые размеры матриц ({size(a)} и {size(b)})")
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def scale(matrix, factor):
    return [[x * factor for x in row] for row in matrix]


def transpose(matrix):
    return [list(column) for column in zip(*matrix)]


def determinant(matrix):
    """Точный определитель методом Гаусса на дробях."""
    if len(matrix) != len(matrix[0]):
        raise MatrixError(f"определитель есть только у квадратной матрицы, а эта {size(matrix)}")
    exact = all(isinstance(x, int) for row in matrix for x in row)
    rows = [[Fraction(x) for x in row] for row in matrix]
    n = len(rows)
    result = Fraction(1)
    for column in range(n):
        pivot = next((r for r in range(column, n) if rows[r][column] != 0), None)
        if pivot is None:
            return 0 if exact else 0.0
        if pivot != column:
            rows[column], rows[pivot] = rows[pivot], rows[column]
            result = -result
        result *= rows[column][column]
        for r in range(column + 1, n):
            factor = rows[r][column] / rows[column][column]
            if factor:
                rows[r] = [x - factor * y for x, y in zip(rows[r], rows[column])]
    return int(result) if exact else float(result)


def check(matrix):
    for row in matrix:
        for x in row:
            if isinstance(x, float) and not math.isfinite(x):
                raise MatrixError("элемент матрицы слишком большой")
    return matrix


def evaluate(text):
    """Результат команды matrix: матрица (список строк) или число (определитель)."""
    parser = Parser(text)
    kind, word = parser.peek()
    if kind == "word":
        parser.take()
        command = word.lower()
        if command not in ("det", "transpose", "t"):
            raise MatrixError(f"неизвестная операция «{word}»; есть +, -, *, det, transpose")
        value = parser.operand()
        if not parser.done():
            raise MatrixError(f"после {command} нужна одна матрица")
        if not is_matrix(value):
            raise MatrixError(f"{command}: нужна матрица, а не число")
        return determinant(value) if command == "det" else transpose(value)
    left = parser.operand()
    if parser.done():
        if not is_matrix(left):
            raise MatrixError("нужна хотя бы одна матрица")
        return left
    kind, op = parser.take()
    if kind != "op":
        raise MatrixError(f"между матрицами нужна операция +, - или *, а не «{op}»")
    right = parser.operand()
    if not parser.done():
        raise MatrixError("за одну команду выполняется одна операция")
    if op in "+-":
        if not (is_matrix(left) and is_matrix(right)):
            raise MatrixError("складывать и вычитать можно только матрицы одного размера")
        return check(add(left, right, 1 if op == "+" else -1))
    if is_matrix(left) and is_matrix(right):
        return check(multiply(left, right))
    if is_matrix(left):
        return check(scale(left, right))
    if is_matrix(right):
        return check(scale(right, left))
    raise MatrixError("нужна хотя бы одна матрица")


def format_matrix(matrix, format_element, one_line=False):
    """[[6, 8],\\n   [10, 12]] (или в одну строку для истории)."""
    rows = ["[" + ", ".join(format_element(x) for x in row) + "]" for row in matrix]
    separator = ", " if one_line else ",\n   "
    return "[" + separator.join(rows) + "]"
