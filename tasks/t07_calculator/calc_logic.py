import math
import re
from typing import Any, Optional, Union

NUM_RE = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
CMP_OPS = ("<=", ">=", "==", "!=", "<", ">")


class LogicError(Exception):
    pass


def has_logic_construct(expr: str) -> bool:
    for op in ("<=", ">=", "==", "!=", "<", ">"):
        if op in expr:
            return True
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr):
        if word.lower() in ("and", "or", "not", "true", "false"):
            return True
    return False


def _tokenize_logic(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue

        if i + 1 < n and expr[i:i + 2] in ("<=", ">=", "==", "!="):
            tokens.append(("CMP", expr[i:i + 2]))
            i += 2
            continue

        if ch in "<>":
            tokens.append(("CMP", ch))
            i += 1
            continue

        if ch in "+-*/^()":
            if ch == "*" and i + 1 < n and expr[i + 1] == "*":
                tokens.append(("OP", "^"))
                i += 2
            elif ch in "+-*/^":
                tokens.append(("OP", ch))
                i += 1
            elif ch == "(":
                tokens.append(("LPAREN", "("))
                i += 1
            elif ch == ")":
                tokens.append(("RPAREN", ")"))
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
                    raise LogicError("некорректная экспонента в числе")
            if i < n and (expr[i].isalpha() or expr[i] in "_."):
                raise LogicError("некорректный числовой литерал")
            tokens.append(("NUM", expr[start:i]))
            continue

        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ch == "_":
            start = i
            while i < n and (("a" <= expr[i] <= "z") or ("A" <= expr[i] <= "Z") or ("0" <= expr[i] <= "9") or expr[i] == "_"):
                i += 1
            word = expr[start:i]
            low = word.lower()
            if low == "and":
                tokens.append(("AND", "AND"))
            elif low == "or":
                tokens.append(("OR", "OR"))
            elif low == "not":
                tokens.append(("NOT", "NOT"))
            elif low == "true":
                tokens.append(("BOOL", "true"))
            elif low == "false":
                tokens.append(("BOOL", "false"))
            else:
                tokens.append(("IDENT", word))
            continue

        raise LogicError(f"недопустимый символ '{ch}' в логическом выражении")

    return tokens


class _LogicParser:
    def __init__(self, tokens: list[tuple[str, str]], variables: dict[str, Any]):
        self.tokens = tokens
        self.pos = 0
        self.vars = variables

    def peek(self) -> Optional[tuple[str, str]]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self) -> tuple[str, str]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> bool:
        if not self.tokens:
            raise LogicError("пустое логическое выражение")
        val = self.parse_or()
        if self.peek() is not None:
            raise LogicError(f"неожиданный токен '{self.peek()[1]}'")
        if not isinstance(val, bool):
            raise LogicError("результат выражения не является логическим значением")
        return val

    def parse_or(self) -> Any:
        left = self.parse_and()
        while self.peek() and self.peek()[0] == "OR":
            self.consume()
            right = self.parse_and()
            if not isinstance(left, bool) or not isinstance(right, bool):
                raise LogicError("оператор OR применим только к логическим значениям")
            left = left or right
        return left

    def parse_and(self) -> Any:
        left = self.parse_not()
        while self.peek() and self.peek()[0] == "AND":
            self.consume()
            right = self.parse_not()
            if not isinstance(left, bool) or not isinstance(right, bool):
                raise LogicError("оператор AND применим только к логическим значениям")
            left = left and right
        return left

    def parse_not(self) -> Any:
        if self.peek() and self.peek()[0] == "NOT":
            self.consume()
            val = self.parse_not()
            if not isinstance(val, bool):
                raise LogicError("оператор NOT применим только к логическому значению")
            return not val
        return self.parse_comparison()

    def parse_comparison(self) -> Any:
        left = self.parse_add()
        tok = self.peek()
        if tok and tok[0] == "CMP":
            op = self.consume()[1]
            right = self.parse_add()
            if self.peek() and self.peek()[0] == "CMP":
                raise LogicError("цепочки сравнений не поддерживаются")

            if isinstance(left, bool) or isinstance(right, bool):
                if not (isinstance(left, bool) and isinstance(right, bool)):
                    raise LogicError("нельзя сравнивать логическое значение с числом")
                if op == "==":
                    return left == right
                if op == "!=":
                    return left != right
                raise LogicError(f"оператор '{op}' не применим к логическим значениям")

            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
        return left

    def _ensure_number(self, val: Any) -> Union[int, float]:
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise LogicError("арифметическая операция применима только к числам")
        return val

    def parse_add(self) -> Any:
        left = self.parse_mul()
        while self.peek() and self.peek()[0] == "OP" and self.peek()[1] in ("+", "-"):
            op = self.consume()[1]
            right = self.parse_mul()
            a = self._ensure_number(left)
            b = self._ensure_number(right)
            left = a + b if op == "+" else a - b
        return left

    def parse_mul(self) -> Any:
        left = self.parse_unary()
        while self.peek() and self.peek()[0] == "OP" and self.peek()[1] in ("*", "/"):
            op = self.consume()[1]
            right = self.parse_unary()
            a = self._ensure_number(left)
            b = self._ensure_number(right)
            if op == "*":
                left = a * b
            else:
                if b == 0:
                    raise LogicError("деление на ноль")
                left = float(a) / float(b)
        return left

    def parse_unary(self) -> Any:
        if self.peek() and self.peek()[0] == "OP" and self.peek()[1] in ("+", "-"):
            op = self.consume()[1]
            val = self.parse_unary()
            num = self._ensure_number(val)
            return -num if op == "-" else num
        return self.parse_power()

    def parse_power(self) -> Any:
        base = self.parse_primary()
        if self.peek() and self.peek()[0] == "OP" and self.peek()[1] == "^":
            self.consume()
            exp = self.parse_unary()
            a = self._ensure_number(base)
            b = self._ensure_number(exp)
            if a == 0 and b <= 0:
                raise LogicError("недопустимое возведение нуля в степень")
            return a ** b
        return base

    def parse_primary(self) -> Any:
        tok = self.peek()
        if tok is None:
            raise LogicError("неожиданный конец выражения")

        kind, text = tok
        if kind == "BOOL":
            self.consume()
            return text == "true"

        if kind == "NUM":
            self.consume()
            if "." not in text and "e" not in text and "E" not in text:
                return int(text)
            return float(text)

        if kind == "LPAREN":
            self.consume()
            val = self.parse_or()
            nxt = self.peek()
            if nxt is None or nxt[0] != "RPAREN":
                raise LogicError("не закрыта скобка ')'")
            self.consume()
            return val

        if kind == "IDENT":
            self.consume()
            if self.peek() and self.peek()[0] == "LPAREN":
                raise LogicError(f"вызов функции '{text}' не поддерживается в логическом выражении")
            if text in self.vars:
                return self.vars[text]
            if text == "pi":
                return math.pi
            if text == "e":
                return math.e
            raise LogicError(f"неизвестная переменная '{text}'")

        raise LogicError(f"неожиданный токен '{text}'")


def evaluate_logic(expr: str, variables: Optional[dict[str, Any]] = None) -> bool:
    tokens = _tokenize_logic(expr)
    parser = _LogicParser(tokens, variables or {})
    return parser.parse()