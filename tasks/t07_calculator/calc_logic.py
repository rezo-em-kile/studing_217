"""Логический калькулятор: AND, OR, NOT, true/false и сравнения чисел.

Приоритет (от слабого к сильному): OR → AND → NOT → сравнения.
Модуль не зависит от остальных модулей калькулятора: числовые операнды сравнений
(«x > 5», «-x < 0») вычисляет функция number_of(текст), которую передаёт вызывающая программа.

    or_expr  := and_expr (OR and_expr)*
    and_expr := not_expr (AND not_expr)*
    not_expr := NOT not_expr | compare
    compare  := operand (СРАВНЕНИЕ operand)?
    operand  := '(' or_expr ')' | true | false | логическая переменная | числовое выражение
"""
import re

KEYWORDS = ("and", "or", "not", "true", "false")
COMPARISONS = ("<=", ">=", "==", "!=", "<", ">")
TOKEN_RE = re.compile(r"\s*(?:(?P<cmp><=|>=|==|!=|<|>)|(?P<paren>[()])|(?P<word>[^\W\d]\w*)"
                      r"|(?P<other>[^\s()<>=!\w]+|[0-9.][\w.]*|[=!]))")


class LogicError(Exception):
    """Ошибка в логическом выражении."""


def looks_logical(text):
    """Есть ли в выражении логические слова или сравнения."""
    if re.search(r"[<>=!]", text):
        return True
    return any(word.lower() in KEYWORDS for word in re.findall(r"[^\W\d]\w*", text))


def tokenize(text):
    tokens = []
    position = 0
    text = text.rstrip()
    while position < len(text):
        match = TOKEN_RE.match(text, position)
        if not match:
            raise LogicError(f"недопустимый символ «{text[position:].strip()[:1]}»")
        kind = match.lastgroup
        value = match.group(kind)
        start = match.start(kind)
        if kind == "word" and value.lower() in KEYWORDS:
            kind = value.lower()
        if kind == "other" and value in ("=", "!"):
            raise LogicError(f"недопустимый оператор «{value}», сравнения: {', '.join(COMPARISONS)}")
        tokens.append((kind, value, start, match.end()))
        position = match.end()
    return tokens


class Parser:
    def __init__(self, text, variables, number_of):
        self.text = text
        self.tokens = tokenize(text)
        self.position = 0
        self.variables = variables
        self.number_of = number_of

    def peek(self, offset=0):
        index = self.position + offset
        return self.tokens[index][0] if index < len(self.tokens) else None

    def parse(self):
        if not self.tokens:
            raise LogicError("пустое выражение")
        value = self.or_expr()
        if self.position != len(self.tokens):
            raise LogicError(f"лишнее «{self.tokens[self.position][1]}» в выражении")
        return self.need_bool(value, "результат")

    @staticmethod
    def need_bool(value, where):
        if not isinstance(value, bool):
            raise LogicError(f"{where}: ожидалось true или false, а получено число")
        return value

    def or_expr(self):
        value = self.and_expr()
        while self.peek() == "or":
            self.position += 1
            right = self.and_expr()
            value = self.need_bool(value, "OR") | self.need_bool(right, "OR")
        return value

    def and_expr(self):
        value = self.not_expr()
        while self.peek() == "and":
            self.position += 1
            right = self.not_expr()
            value = self.need_bool(value, "AND") & self.need_bool(right, "AND")
        return value

    def not_expr(self):
        if self.peek() == "not":
            self.position += 1
            return not self.need_bool(self.not_expr(), "NOT")
        return self.compare()

    def compare(self):
        left = self.operand()
        if self.peek() != "cmp":
            return left
        op = self.tokens[self.position][1]
        self.position += 1
        right = self.operand()
        if self.peek() == "cmp":
            raise LogicError("цепочки сравнений (1 < 2 < 3) не поддерживаются, используйте AND")
        if isinstance(left, bool) != isinstance(right, bool):
            raise LogicError(f"нельзя сравнивать число и true/false ({op})")
        if isinstance(left, bool) and op not in ("==", "!="):
            raise LogicError(f"true/false сравниваются только через == и !=, а не {op}")
        return {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right,
                "==": left == right, "!=": left != right}[op]

    def matching_paren(self, start):
        depth = 0
        for index in range(start, len(self.tokens)):
            if self.tokens[index][0] == "paren":
                depth += 1 if self.tokens[index][1] == "(" else -1
                if depth == 0:
                    return index
        raise LogicError("не закрыта скобка «(»")

    def is_logical_group(self, start, end):
        for kind, value, _, _ in self.tokens[start + 1:end]:
            if kind in KEYWORDS or kind == "cmp":
                return True
            if kind == "word" and isinstance(self.variable(value), bool):
                return True
        return False

    def variable(self, name):
        for key, value in self.variables:
            if key == name:
                return value
        return None

    def operand(self):
        kind = self.peek()
        if kind is None:
            raise LogicError("выражение оборвалось: не хватает операнда")
        if kind == "paren" and self.tokens[self.position][1] == "(":
            end = self.matching_paren(self.position)
            if self.is_logical_group(self.position, end):
                self.position += 1
                value = self.or_expr()
                if self.peek() != "paren" or self.tokens[self.position][1] != ")":
                    raise LogicError("ожидалась «)»")
                self.position += 1
                return value
        if kind in ("true", "false"):
            self.position += 1
            return kind == "true"
        if kind in ("and", "or", "not", "cmp") or (kind == "paren" and self.tokens[self.position][1] == ")"):
            raise LogicError(f"неожиданное «{self.tokens[self.position][1]}»: не хватает операнда")
        return self.number_span()

    def number_span(self):
        """Числовой операнд: токены до сравнения, AND/OR/NOT или закрывающей скобки."""
        start = self.position
        depth = 0
        while self.position < len(self.tokens):
            kind, value, _, _ = self.tokens[self.position]
            if kind in ("cmp", "and", "or", "not", "true", "false"):
                break
            if kind == "paren":
                if value == "(":
                    depth += 1
                elif depth == 0:
                    break
                else:
                    depth -= 1
            self.position += 1
        tokens = self.tokens[start:self.position]
        if not tokens:
            raise LogicError("не хватает операнда")
        if len(tokens) == 1 and tokens[0][0] == "word" and isinstance(self.variable(tokens[0][1]), bool):
            return self.variable(tokens[0][1])
        text = self.text[tokens[0][2]:tokens[-1][3]]
        value = self.number_of(text)
        if isinstance(value, bool):
            raise LogicError(f"«{text}» - не число")
        return value


def evaluate(text, variables, number_of):
    """Значение логического выражения: True или False.

    variables - список пар (имя, значение), значение - число или True/False;
    number_of(текст) - вычисляет числовой операнд (ошибки пробрасывает сама).
    """
    return Parser(text, list(variables), number_of).parse()


def format_bool(value):
    return "true" if value else "false"
