import math
import re
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from typing import Union

NUM_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")

Number = Union[int, float]
Matrix = list[list[Number]]


class MatrixError(Exception):
    pass


def _is_int_val(val: Number) -> bool:
    return isinstance(val, int) and not isinstance(val, bool)


def _format_elem_plain(val: Number, precision: int) -> str:
    if _is_int_val(val):
        return str(val)
    x = float(val)
    if x == 0.0:
        return "0.0"
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


def format_matrix_multiline(mat: Matrix, precision: int) -> str:
    rows_str = [
        "[" + ", ".join(_format_elem_plain(x, precision) for x in row) + "]"
        for row in mat
    ]
    return "= [" + ",\n   ".join(rows_str) + "]"


def format_matrix_singleline(mat: Matrix, precision: int) -> str:
    rows_str = [
        "[" + ", ".join(_format_elem_plain(x, precision) for x in row) + "]"
        for row in mat
    ]
    return "[" + ", ".join(rows_str) + "]"


def _parse_scalar(raw: str) -> Number:
    if not NUM_RE.match(raw):
        raise MatrixError(f"некорректное число '{raw}'")
    if "." not in raw and "e" not in raw and "E" not in raw:
        v = int(raw)
        if abs(v) >= 10 ** 1000:
            raise MatrixError("слишком большое число")
        return v
    vf = float(raw)
    if math.isnan(vf) or math.isinf(vf):
        raise MatrixError("числовое переполнение")
    return vf


def _parse_matrix_literal(text: str) -> Matrix:
    s = text.strip()
    if len(s) < 4 or not (s.startswith("[") and s.endswith("]")):
        raise MatrixError("матрица должна быть в формате [[...], [...]]")

    inner = s[1:-1].strip()
    if not inner:
        raise MatrixError("пустая матрица")

    rows: Matrix = []
    i = 0
    n = len(inner)
    while i < n:
        if inner[i] != "[":
            raise MatrixError("ожидалась '[' в начале строки матрицы")
        close_idx = inner.find("]", i + 1)
        if close_idx == -1:
            raise MatrixError("не закрыта строка матрицы ']'")
        row_content = inner[i + 1:close_idx].strip()
        if not row_content:
            raise MatrixError("пустая строка матрицы")
        elems_raw = row_content.split(",")
        row: list[Number] = []
        for er in elems_raw:
            token = er.strip()
            if not token:
                raise MatrixError("лишняя запятая или пустой элемент в строке матрицы")
            row.append(_parse_scalar(token))
        rows.append(row)

        i = close_idx + 1
        while i < n and inner[i].isspace():
            i += 1
        if i < n:
            if inner[i] != ",":
                raise MatrixError("ожидалась запятая между строками матрицы")
            i += 1
            while i < n and inner[i].isspace():
                i += 1
            if i >= n:
                raise MatrixError("лишняя запятая после последней строки матрицы")

    cols = len(rows[0])
    for r in rows:
        if len(r) != cols:
            raise MatrixError("строки матрицы имеют разную длину")
    return rows


def _tokenize_matrix_expr(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue

        if ch == "[":
            depth = 0
            start = i
            while i < n:
                if expr[i] == "[":
                    depth += 1
                elif expr[i] == "]":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            if depth != 0:
                raise MatrixError("не закрыта скобка матрицы ']'")
            tokens.append(("MAT", expr[start:i]))
            continue

        if ch in "+-*":
            # Если знак '-' или '+' относится к числу (в начале или после оператора)
            if ch in "+-" and (not tokens or tokens[-1][0] == "OP"):
                start = i
                i += 1
                while i < n and not expr[i].isspace() and expr[i] not in "+-*[]":
                    i += 1
                tokens.append(("NUM", expr[start:i]))
            else:
                tokens.append(("OP", ch))
                i += 1
            continue

        if ("0" <= ch <= "9") or ch == ".":
            start = i
            while i < n and not expr[i].isspace() and expr[i] not in "[]":
                if expr[i] in "+-" and i > start and expr[i - 1] not in "eE":
                    break
                if expr[i] == "*":
                    break
                i += 1
            tokens.append(("NUM", expr[start:i]))
            continue

        if ch.isalpha():
            start = i
            while i < n and expr[i].isalpha():
                i += 1
            tokens.append(("WORD", expr[start:i].lower()))
            continue

        raise MatrixError(f"недопустимый символ '{ch}' в матричном выражении")

    return tokens


def _add_sub(a: Matrix, b: Matrix, sign: int) -> Matrix:
    ra, ca = len(a), len(a[0])
    rb, cb = len(b), len(b[0])
    if (ra, ca) != (rb, cb):
        raise MatrixError(f"несовместимые размеры матриц ({ra}×{ca} и {rb}×{cb})")
    res: Matrix = []
    for i in range(ra):
        row: list[Number] = []
        for j in range(ca):
            x, y = a[i][j], b[i][j]
            if _is_int_val(x) and _is_int_val(y):
                row.append(x + sign * y)
            else:
                row.append(float(x) + sign * float(y))
        res.append(row)
    return res


def _mul_matrices(a: Matrix, b: Matrix) -> Matrix:
    ra, ca = len(a), len(a[0])
    rb, cb = len(b), len(b[0])
    if ca != rb:
        raise MatrixError(f"несовместимые размеры матриц ({ra}×{ca} и {rb}×{cb})")
    res: Matrix = []
    for i in range(ra):
        row: list[Number] = []
        for j in range(cb):
            all_int = True
            acc_int = 0
            acc_flt = 0.0
            for k in range(ca):
                x, y = a[i][k], b[k][j]
                if all_int and _is_int_val(x) and _is_int_val(y):
                    acc_int += x * y
                else:
                    if all_int:
                        acc_flt = float(acc_int)
                        all_int = False
                    acc_flt += float(x) * float(y)
            row.append(acc_int if all_int else acc_flt)
        res.append(row)
    return res


def _mul_scalar(mat: Matrix, scalar: Number) -> Matrix:
    res: Matrix = []
    for r in mat:
        row: list[Number] = []
        for x in r:
            if _is_int_val(x) and _is_int_val(scalar):
                row.append(x * scalar)
            else:
                row.append(float(x) * float(scalar))
        res.append(row)
    return res


def _transpose(mat: Matrix) -> Matrix:
    ra, ca = len(mat), len(mat[0])
    return [[mat[i][j] for i in range(ra)] for j in range(ca)]


def _determinant(mat: Matrix) -> Number:
    ra, ca = len(mat), len(mat[0])
    if ra != ca:
        raise MatrixError(f"определитель существует только для квадратной матрицы ({ra}×{ca})")

    n = ra
    all_int = all(_is_int_val(mat[i][j]) for i in range(n) for j in range(n))
    work: list[list[Fraction]] = [
        [Fraction(mat[i][j]) if _is_int_val(mat[i][j]) else Fraction(str(mat[i][j])) for j in range(n)]
        for i in range(n)
    ]

    det = Fraction(1)
    for col in range(n):
        pivot_row = None
        for r in range(col, n):
            if work[r][col] != 0:
                pivot_row = r
                break
        if pivot_row is None:
            return 0 if all_int else 0.0
        if pivot_row != col:
            work[col], work[pivot_row] = work[pivot_row], work[col]
            det = -det
        pivot = work[col][col]
        det *= pivot
        for r in range(col + 1, n):
            factor = work[r][col] / pivot
            for c in range(col, n):
                work[r][c] -= factor * work[col][c]

    if all_int:
        return int(det)
    return float(det)


def evaluate_matrix_command(rest: str, precision: int) -> tuple[str, str]:
    tokens = _tokenize_matrix_expr(rest)
    if not tokens:
        raise MatrixError("не указано матричное выражение")

    # Унарная операция det / transpose / t
    if tokens[0][0] == "WORD":
        op = tokens[0][1]
        if op not in ("det", "transpose", "t"):
            raise MatrixError(f"неизвестная матричная операция '{op}'")
        if len(tokens) != 2 or tokens[1][0] != "MAT":
            raise MatrixError(f"операция '{op}' ожидает одну матрицу")
        mat = _parse_matrix_literal(tokens[1][1])
        if op == "det":
            d = _determinant(mat)
            s = _format_elem_plain(d, precision)
            return f"= {s}", s
        tr = _transpose(mat)
        return format_matrix_multiline(tr, precision), format_matrix_singleline(tr, precision)

    # Одиночная матрица
    if len(tokens) == 1:
        if tokens[0][0] != "MAT":
            raise MatrixError("ожидалась матрица")
        mat = _parse_matrix_literal(tokens[0][1])
        return format_matrix_multiline(mat, precision), format_matrix_singleline(mat, precision)

    # Бинарная операция
    if len(tokens) != 3 or tokens[1][0] != "OP":
        raise MatrixError("некорректное матричное выражение")

    left_tok, op_tok, right_tok = tokens
    op = op_tok[1]

    if op in ("+", "-"):
        if left_tok[0] != "MAT" or right_tok[0] != "MAT":
            raise MatrixError(f"операция '{op}' применима только к двум матрицам")
        m1 = _parse_matrix_literal(left_tok[1])
        m2 = _parse_matrix_literal(right_tok[1])
        res = _add_sub(m1, m2, 1 if op == "+" else -1)
        return format_matrix_multiline(res, precision), format_matrix_singleline(res, precision)

    if op == "*":
        if left_tok[0] == "MAT" and right_tok[0] == "MAT":
            m1 = _parse_matrix_literal(left_tok[1])
            m2 = _parse_matrix_literal(right_tok[1])
            res = _mul_matrices(m1, m2)
            return format_matrix_multiline(res, precision), format_matrix_singleline(res, precision)
        if left_tok[0] == "MAT" and right_tok[0] == "NUM":
            m1 = _parse_matrix_literal(left_tok[1])
            sc = _parse_scalar(right_tok[1])
            res = _mul_scalar(m1, sc)
            return format_matrix_multiline(res, precision), format_matrix_singleline(res, precision)
        if left_tok[0] == "NUM" and right_tok[0] == "MAT":
            sc = _parse_scalar(left_tok[1])
            m1 = _parse_matrix_literal(right_tok[1])
            res = _mul_scalar(m1, sc)
            return format_matrix_multiline(res, precision), format_matrix_singleline(res, precision)
        raise MatrixError("некорректные операнды для умножения матриц")

    raise MatrixError(f"неподдерживаемая операция '{op}'")