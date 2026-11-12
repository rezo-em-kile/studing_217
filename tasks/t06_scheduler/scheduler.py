"""Планировщик задач с зависимостями.

Режим 1: python scheduler.py tasks.txt   - план по списку задач из файла.
Режим 2: python scheduler.py < commands  - диалог: add, dep, undep, remove, done, fail, reset,
         status, ready, order, stages, plan, deadline, overdue, save, load.

Все обходы графа - без рекурсии (цепочки в десятки тысяч задач).
"""
import heapq
import json
import re
import sys
from datetime import date

PENDING, DONE, FAILED = "ожидает", "выполнена", "провалена"
BLOCKED = "заблокирована"
STATUSES = (PENDING, DONE, FAILED)

NAME_RE = re.compile(r"^[^\s,]+$")
DATE_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
LINE_RE = re.compile(
    r'^задача\s+(?P<name>[^\s,:]+)\s*:\s*"(?P<title>.*)"\s*-\s*зависит\s+от\s*:\s*(?P<deps>.*)$',
    re.IGNORECASE)


class InputError(Exception):
    """Ошибка в файле задач (код 1)."""


class CommandError(Exception):
    """Ошибка в команде диалога: состояние не меняется."""


class Task:
    def __init__(self, name, title="", deps=None, status=PENDING, deadline=None):
        self.name = name
        self.title = title
        self.deps = list(deps or [])
        self.status = status
        self.deadline = deadline


def parse_date(text):
    match = DATE_RE.match(text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


class Scheduler:
    def __init__(self):
        self.tasks = {}

    # --- граф ---

    def dependents(self):
        """Обратные рёбра: задача -> задачи, которые от неё зависят."""
        result = {name: [] for name in self.tasks}
        for task in self.tasks.values():
            for dep in task.deps:
                result[dep].append(task.name)
        return result

    def topological(self):
        """Порядок выполнения (из доступных - наименьшее имя) и этапы; None при цикле."""
        indegree = {name: len(task.deps) for name, task in self.tasks.items()}
        users = self.dependents()
        heap = [name for name, count in indegree.items() if count == 0]
        heapq.heapify(heap)
        order = []
        stage = {}
        while heap:
            name = heapq.heappop(heap)
            order.append(name)
            stage[name] = 1 + max((stage[dep] for dep in self.tasks[name].deps), default=0)
            for user in users[name]:
                indegree[user] -= 1
                if indegree[user] == 0:
                    heapq.heappush(heap, user)
        if len(order) != len(self.tasks):
            return None, None
        return order, stage

    def find_cycle(self):
        """Любой цикл: список имён, первое повторяется в конце."""
        order, _ = self.topological()
        if order is not None:
            return None
        placed = set(order or [])
        indegree = {name: len(task.deps) for name, task in self.tasks.items()}
        users = self.dependents()
        queue = [name for name, count in indegree.items() if count == 0]
        while queue:
            name = queue.pop()
            placed.add(name)
            for user in users[name]:
                indegree[user] -= 1
                if indegree[user] == 0:
                    queue.append(user)
        start = next(name for name in self.tasks if name not in placed)
        path, position = [], {}
        current = start
        while current not in position:
            position[current] = len(path)
            path.append(current)
            current = next(dep for dep in self.tasks[current].deps if dep not in placed)
        return path[position[current]:] + [current]

    def path(self, start, goal):
        """Цепочка зависимостей от start до goal или None (обход в ширину)."""
        previous = {start: None}
        queue = [start]
        index = 0
        while index < len(queue):
            name = queue[index]
            index += 1
            if name == goal:
                chain = []
                while name is not None:
                    chain.append(name)
                    name = previous[name]
                return chain[::-1]
            for dep in self.tasks[name].deps:
                if dep not in previous:
                    previous[dep] = name
                    queue.append(dep)
        return None

    def blocked(self):
        """Ожидающие задачи, у которых провалена зависимость (прямо или через цепочку)."""
        users = self.dependents()
        result = set()
        stack = [name for name, task in self.tasks.items() if task.status == FAILED]
        while stack:
            name = stack.pop()
            for user in users[name]:
                if user not in result and self.tasks[user].status == PENDING:
                    result.add(user)
                    stack.append(user)
        return result

    def status_of(self, name, blocked):
        task = self.tasks[name]
        return BLOCKED if task.status == PENDING and name in blocked else task.status

    def ready(self):
        return sorted(name for name, task in self.tasks.items()
                      if task.status == PENDING and all(self.tasks[d].status == DONE for d in task.deps))

    def label(self, name):
        title = self.tasks[name].title
        return f'{name}: "{title}"' if title else name

    def stage_lines(self, stage):
        groups = {}
        for name, number in stage.items():
            groups.setdefault(number, []).append(name)
        return [f"Этап {number}: [{', '.join(sorted(groups[number]))}]" for number in sorted(groups)]

    def plan(self):
        order, stage = self.topological()
        lines = ["Проверка зависимостей: циклов не обнаружено.", "", "Задачи, готовые к выполнению прямо сейчас:"]
        ready = self.ready()
        lines += [f"  ✓ {self.label(name)}" for name in ready] or ["  нет"]
        lines += ["", "Порядок выполнения всех задач (топологическая сортировка):"]
        lines += [f"  {number}. {self.label(name)}" for number, name in enumerate(order, 1)] or ["  нет задач"]
        lines += ["", "Параллельные потоки (что можно делать одновременно):"]
        lines += [f"  {line}" for line in self.stage_lines(stage)] or ["  нет задач"]
        return lines

    # --- команды диалога ---

    def need(self, name):
        if name not in self.tasks:
            raise CommandError(f"задачи {name} нет")
        return self.tasks[name]

    @staticmethod
    def check_name(name):
        if not NAME_RE.match(name):
            raise CommandError(f"неверное имя задачи «{name}»")

    def cmd_add(self, args):
        if not args:
            raise CommandError("формат: add ИМЯ [ЗАВ1 ЗАВ2 …]")
        name, deps = args[0], []
        self.check_name(name)
        if name in self.tasks:
            raise CommandError(f"задача {name} уже есть")
        for dep in args[1:]:
            if dep == name:
                raise CommandError(f"циклическая зависимость: {name} → {name}")
            self.need(dep)
            if dep not in deps:
                deps.append(dep)
        self.tasks[name] = Task(name, deps=deps)
        return [f"Задача {name} добавлена"]

    def cmd_dep(self, args):
        if len(args) != 2:
            raise CommandError("формат: dep ИМЯ ОТ_ЧЕГО")
        name, dep = args
        task = self.need(name)
        self.need(dep)
        if dep not in task.deps:
            chain = self.path(dep, name)
            if chain is not None:
                raise CommandError(f"циклическая зависимость: {' → '.join([name] + chain)}")
            task.deps.append(dep)
        return [f"{name} зависит от {dep}"]

    def cmd_undep(self, args):
        if len(args) != 2:
            raise CommandError("формат: undep ИМЯ ОТ_ЧЕГО")
        name, dep = args
        task = self.need(name)
        self.need(dep)
        if dep not in task.deps:
            raise CommandError(f"{name} не зависит от {dep}")
        task.deps.remove(dep)
        return [f"{name} больше не зависит от {dep}"]

    def cmd_remove(self, args):
        if not 1 <= len(args) <= 2 or (len(args) == 2 and args[1] != "--force"):
            raise CommandError("формат: remove ИМЯ [--force]")
        name = args[0]
        self.need(name)
        users = sorted(user for user, task in self.tasks.items() if name in task.deps)
        if users and len(args) == 1:
            raise CommandError(f"от задачи {name} зависят: {', '.join(users)} (удалить вместе со ссылками: "
                               f"remove {name} --force)")
        del self.tasks[name]
        for user in users:
            self.tasks[user].deps.remove(name)
        return [f"Задача {name} удалена"]

    def single(self, args, command):
        if len(args) != 1:
            raise CommandError(f"формат: {command} ИМЯ")
        return self.need(args[0])

    def cmd_done(self, args):
        task = self.single(args, "done")
        if self.status_of(task.name, self.blocked()) != PENDING:
            raise CommandError(f"задача {task.name} не ожидает выполнения "
                               f"({self.status_of(task.name, self.blocked())})")
        waiting = [dep for dep in task.deps if self.tasks[dep].status != DONE]
        if waiting:
            raise CommandError(f"у задачи {task.name} не выполнены зависимости: {', '.join(sorted(waiting))}")
        task.status = DONE
        return [f"Задача {task.name} выполнена"]

    def cmd_fail(self, args):
        task = self.single(args, "fail")
        before = self.blocked()
        if self.status_of(task.name, before) != PENDING:
            raise CommandError(f"провалить можно только ожидающую задачу, {task.name}: "
                               f"{self.status_of(task.name, before)}")
        task.status = FAILED
        newly = sorted(self.blocked() - before)
        return [f"Задача {task.name} провалена" + (f"; заблокированы: {', '.join(newly)}" if newly else "")]

    def cmd_reset(self, args):
        task = self.single(args, "reset")
        if task.status != FAILED:
            raise CommandError(f"снова ожидать может только проваленная задача, {task.name}: "
                               f"{self.status_of(task.name, self.blocked())}")
        before = self.blocked()
        task.status = PENDING
        freed = sorted(name for name in before - self.blocked() if name != task.name)
        return [f"Задача {task.name} снова ожидает" + (f"; разблокированы: {', '.join(freed)}" if freed else "")]

    def cmd_status(self, args):
        task = self.single(args, "status")
        return [f"{task.name}: {self.status_of(task.name, self.blocked())}"]

    @staticmethod
    def no_args(args, command):
        if args:
            raise CommandError(f"у команды {command} нет параметров")

    def cmd_ready(self, args):
        self.no_args(args, "ready")
        return [f"Готовы к выполнению: {', '.join(self.ready()) or 'нет'}"]

    def cmd_order(self, args):
        self.no_args(args, "order")
        order, _ = self.topological()
        return [f"Порядок: {', '.join(order) or 'нет задач'}"]

    def cmd_stages(self, args):
        self.no_args(args, "stages")
        _, stage = self.topological()
        return self.stage_lines(stage) or ["нет задач"]

    def cmd_plan(self, args):
        self.no_args(args, "plan")
        return self.plan()

    def cmd_deadline(self, args):
        if len(args) != 2:
            raise CommandError("формат: deadline ИМЯ ГГГГ-ММ-ДД")
        task = self.need(args[0])
        day = parse_date(args[1])
        if day is None:
            raise CommandError(f"неверная дата «{args[1]}», нужно ГГГГ-ММ-ДД")
        task.deadline = day
        return [f"Задача {task.name}: дедлайн {day.isoformat()}"]

    def cmd_overdue(self, args):
        if len(args) != 1:
            raise CommandError("формат: overdue ГГГГ-ММ-ДД")
        day = parse_date(args[0])
        if day is None:
            raise CommandError(f"неверная дата «{args[0]}», нужно ГГГГ-ММ-ДД")
        late = sorted(name for name, task in self.tasks.items()
                      if task.status != DONE and task.deadline is not None and task.deadline < day)
        return [f"Просрочены: {', '.join(late) or 'нет'}"]

    def cmd_save(self, args):
        if len(args) != 1:
            raise CommandError("формат: save ФАЙЛ")
        data = {"tasks": [{"name": t.name, "title": t.title, "deps": t.deps, "status": t.status,
                           "deadline": t.deadline.isoformat() if t.deadline else None}
                          for t in self.tasks.values()]}
        try:
            with open(args[0], "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except OSError as error:
            raise CommandError(f"не удалось сохранить в {args[0]}: {error.strerror}") from None
        return [f"Сохранено в {args[0]}"]

    def cmd_load(self, args):
        if len(args) != 1:
            raise CommandError("формат: load ФАЙЛ")
        try:
            with open(args[0], encoding="utf-8") as file:
                data = json.load(file)
        except OSError as error:
            raise CommandError(f"не удалось открыть {args[0]}: {error.strerror}") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CommandError(f"файл {args[0]} - не JSON с сохранённым состоянием") from None
        loaded = Scheduler()
        try:
            loaded.restore(data)
        except (TypeError, KeyError, ValueError, AttributeError):
            raise CommandError(f"файл {args[0]} повреждён или имеет неверную структуру") from None
        self.tasks = loaded.tasks
        return [f"Загружено задач: {len(self.tasks)}"]

    def restore(self, data):
        if not isinstance(data, dict) or not isinstance(data["tasks"], list):
            raise ValueError
        for item in data["tasks"]:
            name, title, deps = item["name"], item["title"], item["deps"]
            status, deadline = item["status"], item["deadline"]
            if not isinstance(name, str) or not NAME_RE.match(name) or name in self.tasks:
                raise ValueError
            if not isinstance(title, str) or not isinstance(deps, list) or status not in STATUSES:
                raise ValueError
            if not all(isinstance(dep, str) for dep in deps) or len(set(deps)) != len(deps):
                raise ValueError
            day = None
            if deadline is not None:
                day = parse_date(deadline) if isinstance(deadline, str) else None
                if day is None:
                    raise ValueError
            self.tasks[name] = Task(name, title, deps, status, day)
        for task in self.tasks.values():
            if any(dep not in self.tasks for dep in task.deps):
                raise ValueError
        if self.topological()[0] is None:
            raise ValueError

    COMMANDS = ("add", "dep", "undep", "remove", "done", "fail", "reset", "status", "ready", "order",
                "stages", "plan", "deadline", "overdue", "save", "load")

    def execute(self, line):
        words = line.split()
        if words[0] not in self.COMMANDS:
            raise CommandError(f"неизвестная команда «{words[0]}»")
        return getattr(self, f"cmd_{words[0]}")(words[1:])


def load_file(path):
    """Читает файл задач (режим 1)."""
    try:
        with open(path, encoding="utf-8-sig") as file:
            lines = file.read().splitlines()
    except OSError as error:
        raise InputError(f"не удалось открыть файл {path}: {error.strerror}") from None
    except UnicodeDecodeError:
        raise InputError(f"файл {path} не в кодировке UTF-8") from None
    scheduler = Scheduler()
    where = {}
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_RE.match(line)
        if not match:
            raise InputError(f"строка {number}: неверный формат, ожидается "
                             f'«Задача ИМЯ: "Название" - зависит от: A, B»')
        name, title, deps_text = match.group("name"), match.group("title"), match.group("deps").strip()
        deps = []
        if deps_text not in ("", "-"):
            for dep in deps_text.split(","):
                dep = dep.strip()
                if not NAME_RE.match(dep):
                    raise InputError(f"строка {number}: задача {name}: неверная зависимость «{dep}»")
                if dep not in deps:
                    deps.append(dep)
        if name in scheduler.tasks:
            raise InputError(f"строка {number}: задача {name} уже описана в строке {where[name]}")
        where[name] = number
        scheduler.tasks[name] = Task(name, title, deps)
    for task in scheduler.tasks.values():
        for dep in task.deps:
            if dep not in scheduler.tasks:
                raise InputError(f"строка {where[task.name]}: задача {task.name} зависит от "
                                 f"несуществующей задачи {dep}")
    return scheduler


def use_utf8_streams():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")


def main():
    use_utf8_streams()
    args = sys.argv[1:]
    if len(args) > 1:
        print("Ошибка: слишком много аргументов; использование: python scheduler.py [tasks.txt]",
              file=sys.stderr)
        sys.exit(2)
    if args:
        try:
            scheduler = load_file(args[0])
        except InputError as error:
            print(f"Ошибка: {error}", file=sys.stderr)
            sys.exit(1)
        cycle = scheduler.find_cycle()
        if cycle:
            print("ОШИБКА: обнаружена циклическая зависимость!")
            print(f"Цепочка: {' → '.join(cycle)}")
            print("Невозможно определить порядок выполнения.")
            sys.exit(1)
        for line in scheduler.plan():
            print(line)
        return
    scheduler = Scheduler()
    first = True
    for raw in sys.stdin:
        line = (raw.lstrip("﻿") if first else raw).strip()
        first = False
        if not line:
            continue
        try:
            answer = scheduler.execute(line)
        except CommandError as error:
            answer = [f"ОШИБКА: {error}"]
        for text in answer:
            print(text, flush=True)


if __name__ == "__main__":
    main()
