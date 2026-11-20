import heapq
import json
import re
import sys
from collections import deque
from datetime import datetime
from typing import Optional

FILE_LINE_RE = re.compile(
    r"^\s*задача\s+(?P<name>[^\s,:]+)\s*:\s*\"(?P<title>[^\"]*)\"\s*-\s*зависит\s+от\s*:\s*(?P<deps>.*)\s*$",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date(raw: str) -> bool:
    if not DATE_RE.match(raw):
        return False
    try:
        datetime.strptime(raw, "%Y-%m-%d")
        return True
    except ValueError:
        return False


class Scheduler:
    def __init__(self) -> None:
        self.deps: dict[str, list[str]] = {}
        self.titles: dict[str, str] = {}
        self.status: dict[str, str] = {}  # "waiting", "done", "failed"
        self.deadlines: dict[str, Optional[str]] = {}

    def _build_reverse_adj(self) -> dict[str, list[str]]:
        rev: dict[str, list[str]] = {t: [] for t in self.deps}
        for t, d_list in self.deps.items():
            for d in d_list:
                if d in rev:
                    rev[d].append(t)
        return rev

    def find_cycle(self) -> Optional[list[str]]:
        """Итеративный поиск любого цикла в графе зависимостей (u -> d, где u зависит от d)."""
        color: dict[str, int] = {t: 0 for t in self.deps}  # 0=white, 1=gray, 2=black
        parent: dict[str, Optional[str]] = {}

        for start in sorted(self.deps):
            if color[start] != 0:
                continue
            stack: list[tuple[str, int]] = [(start, 0)]
            color[start] = 1
            parent[start] = None

            while stack:
                u, idx = stack[-1]
                neighbors = self.deps[u]
                if idx < len(neighbors):
                    stack[-1] = (u, idx + 1)
                    v = neighbors[idx]
                    if color[v] == 0:
                        color[v] = 1
                        parent[v] = u
                        stack.append((v, 0))
                    elif color[v] == 1:
                        # Восстанавливаем цикл v -> ... -> u -> v
                        chain = [v]
                        cur: Optional[str] = u
                        while cur is not None and cur != v:
                            chain.append(cur)
                            cur = parent.get(cur)
                        chain.append(v)
                        chain.reverse()
                        return chain
                else:
                    color[u] = 2
                    stack.pop()
        return None

    def find_path(self, start: str, goal: str) -> Optional[list[str]]:
        """Итеративный поиск пути по зависимостям от start к goal (start -> ... -> goal)."""
        if start == goal:
            return [start]
        visited = {start}
        parent: dict[str, Optional[str]] = {start: None}
        q: deque[str] = deque([start])

        while q:
            u = q.popleft()
            for v in self.deps.get(u, ()):
                if v == goal:
                    path = [goal]
                    cur: Optional[str] = u
                    while cur is not None:
                        path.append(cur)
                        cur = parent[cur]
                    path.reverse()
                    return path
                if v not in visited:
                    visited.add(v)
                    parent[v] = u
                    q.append(v)
        return None

    def topo_order(self) -> list[str]:
        """Топологическая сортировка (алгоритм Кана с min-heap по имени задачи)."""
        rev = self._build_reverse_adj()
        in_deg: dict[str, int] = {t: len(d_list) for t, d_list in self.deps.items()}
        heap = [t for t, deg in in_deg.items() if deg == 0]
        heapq.heapify(heap)

        result: list[str] = []
        while heap:
            u = heapq.heappop(heap)
            result.append(u)
            for nxt in rev[u]:
                in_deg[nxt] -= 1
                if in_deg[nxt] == 0:
                    heapq.heappush(heap, nxt)
        return result

    def compute_stages(self, order: Optional[list[str]] = None) -> list[list[str]]:
        if order is None:
            order = self.topo_order()
        if not order:
            return []
        stage_num: dict[str, int] = {}
        max_stage = 0
        for t in order:
            st = 1 + max((stage_num[d] for d in self.deps[t]), default=0)
            stage_num[t] = st
            if st > max_stage:
                max_stage = st

        stages: list[list[str]] = [[] for _ in range(max_stage)]
        for t, st in stage_num.items():
            stages[st - 1].append(t)
        for s in stages:
            s.sort()
        return stages

    def compute_blocked_set(self) -> set[str]:
        """Множество ожидающих задач, у которых есть проваленная зависимость (прямая или транзитивная)."""
        rev = self._build_reverse_adj()
        failed_roots = [t for t, st in self.status.items() if st == "failed"]
        if not failed_roots:
            return set()
        visited = set(failed_roots)
        q: deque[str] = deque(failed_roots)
        blocked: set[str] = set()

        while q:
            u = q.popleft()
            for nxt in rev[u]:
                if nxt not in visited:
                    visited.add(nxt)
                    q.append(nxt)
                    if self.status[nxt] == "waiting":
                        blocked.add(nxt)
        return blocked

    def effective_status(self, task: str, blocked_set: Optional[set[str]] = None) -> str:
        st = self.status[task]
        if st == "waiting":
            if blocked_set is None:
                blocked_set = self.compute_blocked_set()
            if task in blocked_set:
                return "blocked"
        return st

    def ready_tasks(self) -> list[str]:
        res: list[str] = []
        for t, st in self.status.items():
            if st == "waiting" and all(self.status[d] == "done" for d in self.deps[t]):
                res.append(t)
        res.sort()
        return res

    def format_task_label(self, task: str) -> str:
        title = self.titles.get(task, "")
        return f'{task}: "{title}"' if title else task

    def format_plan(self) -> list[str]:
        order = self.topo_order()
        stages = self.compute_stages(order)
        ready = sorted(t for t, d_list in self.deps.items() if not d_list)

        lines = [
            "Проверка зависимостей: циклов не обнаружено.",
            "",
            "Задачи, готовые к выполнению прямо сейчас:",
        ]
        if not ready:
            lines.append("  нет")
        else:
            for t in ready:
                lines.append(f"  ✓ {self.format_task_label(t)}")

        lines.append("")
        lines.append("Порядок выполнения всех задач (топологическая сортировка):")
        if not order:
            lines.append("  нет задач")
        else:
            for idx, t in enumerate(order, 1):
                lines.append(f"  {idx}. {self.format_task_label(t)}")

        lines.append("")
        lines.append("Параллельные потоки (что можно делать одновременно):")
        if not stages:
            lines.append("  нет задач")
        else:
            for idx, st_tasks in enumerate(stages, 1):
                lines.append(f"  Этап {idx}: [{', '.join(st_tasks)}]")

        return lines

    # --- Команды диалога ---
    def execute_command(self, raw_line: str) -> list[str]:
        parts = raw_line.strip().split()
        if not parts:
            return []
        cmd = parts[0]

        if cmd == "add":
            if len(parts) < 2:
                return ["ОШИБКА: не указано имя задачи"]
            name = parts[1]
            dep_args = parts[2:]
            if name in self.deps:
                return [f"ОШИБКА: задача '{name}' уже существует"]
            unique_deps: list[str] = []
            seen: set[str] = set()
            for d in dep_args:
                if d == name:
                    return [f"ОШИБКА: циклическая зависимость: {name} → {name}"]
                if d not in self.deps:
                    return [f"ОШИБКА: задача '{d}' не найдена"]
                if d not in seen:
                    seen.add(d)
                    unique_deps.append(d)
            self.deps[name] = unique_deps
            self.titles[name] = ""
            self.status[name] = "waiting"
            self.deadlines[name] = None
            return [f"Задача {name} добавлена"]

        if cmd == "dep":
            if len(parts) != 3:
                return ["ОШИБКА: неверный формат команды dep"]
            a, b = parts[1], parts[2]
            if a not in self.deps:
                return [f"ОШИБКА: задача '{a}' не найдена"]
            if b not in self.deps:
                return [f"ОШИБКА: задача '{b}' не найдена"]
            if b in self.deps[a]:
                return [f"{a} зависит от {b}"]
            if a == b:
                return [f"ОШИБКА: циклическая зависимость: {a} → {a}"]
            path = self.find_path(b, a)
            if path is not None:
                chain = " → ".join([a] + path)
                return [f"ОШИБКА: циклическая зависимость: {chain}"]
            self.deps[a].append(b)
            return [f"{a} зависит от {b}"]

        if cmd == "undep":
            if len(parts) != 3:
                return ["ОШИБКА: неверный формат команды undep"]
            a, b = parts[1], parts[2]
            if a not in self.deps or b not in self.deps:
                return ["ОШИБКА: задача не найдена"]
            if b not in self.deps[a]:
                return [f"ОШИБКА: {a} не зависит от {b}"]
            self.deps[a].remove(b)
            return [f"{a} больше не зависит от {b}"]

        if cmd == "remove":
            if len(parts) not in (2, 3):
                return ["ОШИБКА: неверный формат команды remove"]
            name = parts[1]
            force = False
            if len(parts) == 3:
                if parts[2] != "--force":
                    return [f"ОШИБКА: неизвестный флаг '{parts[2]}'"]
                force = True
            if name not in self.deps:
                return [f"ОШИБКА: задача '{name}' не найдена"]
            dependents = sorted(t for t, d_list in self.deps.items() if name in d_list)
            if dependents and not force:
                return [f"ОШИБКА: от задачи {name} зависят: {', '.join(dependents)}"]
            del self.deps[name]
            self.titles.pop(name, None)
            self.status.pop(name, None)
            self.deadlines.pop(name, None)
            for t in self.deps:
                if name in self.deps[t]:
                    self.deps[t] = [d for d in self.deps[t] if d != name]
            return [f"Задача {name} удалена"]

        if cmd == "done":
            if len(parts) != 2:
                return ["ОШИБКА: неверный формат команды done"]
            name = parts[1]
            if name not in self.deps:
                return [f"ОШИБКА: задача '{name}' не найдена"]
            eff = self.effective_status(name)
            if eff != "waiting":
                return [f"ОШИБКА: задачу '{name}' нельзя выполнить (текущий статус: {eff})"]
            unmet = sorted(d for d in self.deps[name] if self.status[d] != "done")
            if unmet:
                return [f"ОШИБКА: не выполнены зависимости: {', '.join(unmet)}"]
            self.status[name] = "done"
            return [f"Задача {name} выполнена"]

        if cmd == "fail":
            if len(parts) != 2:
                return ["ОШИБКА: неверный формат команды fail"]
            name = parts[1]
            if name not in self.deps:
                return [f"ОШИБКА: задача '{name}' не найдена"]
            before_blocked = self.compute_blocked_set()
            eff = self.effective_status(name, before_blocked)
            if eff != "waiting":
                return [f"ОШИБКА: задачу '{name}' нельзя пометить проваленной"]
            self.status[name] = "failed"
            after_blocked = self.compute_blocked_set()
            newly_blocked = sorted(after_blocked - before_blocked)
            if newly_blocked:
                return [f"Задача {name} провалена; заблокированы: {', '.join(newly_blocked)}"]
            return [f"Задача {name} провалена"]

        if cmd == "reset":
            if len(parts) != 2:
                return ["ОШИБКА: неверный формат команды reset"]
            name = parts[1]
            if name not in self.deps:
                return [f"ОШИБКА: задача '{name}' не найдена"]
            if self.status[name] != "failed":
                return [f"ОШИБКА: сбросить можно только проваленную задачу"]
            before_blocked = self.compute_blocked_set()
            self.status[name] = "waiting"
            after_blocked = self.compute_blocked_set()
            unblocked = sorted(before_blocked - after_blocked)
            if unblocked:
                return [f"Задача {name} снова ожидает; разблокированы: {', '.join(unblocked)}"]
            return [f"Задача {name} снова ожидает"]

        if cmd == "status":
            if len(parts) != 2:
                return ["ОШИБКА: неверный формат команды status"]
            name = parts[1]
            if name not in self.deps:
                return [f"ОШИБКА: задача '{name}' не найдена"]
            eff = self.effective_status(name)
            ru = {
                "waiting": "ожидает",
                "done": "выполнена",
                "failed": "провалена",
                "blocked": "заблокирована",
            }[eff]
            return [f"{name}: {ru}"]

        if cmd == "ready":
            if len(parts) != 1:
                return ["ОШИБКА: неверный формат команды ready"]
            r = self.ready_tasks()
            return [f"Готовы к выполнению: {', '.join(r) if r else 'нет'}"]

        if cmd == "order":
            if len(parts) != 1:
                return ["ОШИБКА: неверный формат команды order"]
            o = self.topo_order()
            return [f"Порядок: {', '.join(o) if o else 'нет задач'}"]

        if cmd == "stages":
            if len(parts) != 1:
                return ["ОШИБКА: неверный формат команды stages"]
            st = self.compute_stages()
            if not st:
                return ["нет задач"]
            return [f"Этап {idx}: [{', '.join(tasks)}]" for idx, tasks in enumerate(st, 1)]

        if cmd == "plan":
            if len(parts) != 1:
                return ["ОШИБКА: неверный формат команды plan"]
            return self.format_plan()

        if cmd == "deadline":
            if len(parts) != 3:
                return ["ОШИБКА: неверный формат команды deadline"]
            name, date_str = parts[1], parts[2]
            if name not in self.deps:
                return [f"ОШИБКА: задача '{name}' не найдена"]
            if not validate_date(date_str):
                return [f"ОШИБКА: некорректная дата '{date_str}'"]
            self.deadlines[name] = date_str
            return [f"Задача {name}: дедлайн {date_str}"]

        if cmd == "overdue":
            if len(parts) != 2:
                return ["ОШИБКА: неверный формат команды overdue"]
            date_str = parts[1]
            if not validate_date(date_str):
                return [f"ОШИБКА: некорректная дата '{date_str}'"]
            res = sorted(
                t for t, dl in self.deadlines.items()
                if dl is not None and dl < date_str and self.status[t] != "done"
            )
            return [f"Просрочены: {', '.join(res) if res else 'нет'}"]

        if cmd == "save":
            if len(parts) != 2:
                return ["ОШИБКА: неверный формат команды save"]
            path = parts[1]
            payload = {
                "tasks": [
                    {
                        "name": t,
                        "title": self.titles.get(t, ""),
                        "deps": self.deps[t],
                        "status": self.status[t],
                        "deadline": self.deadlines.get(t),
                    }
                    for t in self.deps
                ]
            }
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            except OSError as e:
                return [f"ОШИБКА: не удалось сохранить файл '{path}': {e}"]
            return [f"Сохранено в {path}"]

        if cmd == "load":
            if len(parts) != 2:
                return ["ОШИБКА: неверный формат команды load"]
            path = parts[1]
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
                return [f"ОШИБКА: не удалось загрузить файл '{path}': {e}"]

            if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
                return ["ОШИБКА: некорректный формат файла состояния"]

            new_deps: dict[str, list[str]] = {}
            new_titles: dict[str, str] = {}
            new_status: dict[str, str] = {}
            new_deadlines: dict[str, Optional[str]] = {}

            for item in data["tasks"]:
                if not isinstance(item, dict):
                    return ["ОШИБКА: некорректный элемент в файле состояния"]
                t_name = item.get("name")
                t_title = item.get("title", "")
                t_deps = item.get("deps", [])
                t_status = item.get("status", "waiting")
                t_dl = item.get("deadline")
                if (
                    not isinstance(t_name, str)
                    or not t_name
                    or not isinstance(t_title, str)
                    or not isinstance(t_deps, list)
                    or not all(isinstance(d, str) for d in t_deps)
                    or t_status not in ("waiting", "done", "failed")
                    or (t_dl is not None and (not isinstance(t_dl, str) or not validate_date(t_dl)))
                ):
                    return ["ОШИБКА: повреждённые данные задачи в файле состояния"]
                new_deps[t_name] = list(t_deps)
                new_titles[t_name] = t_title
                new_status[t_name] = t_status
                new_deadlines[t_name] = t_dl

            for t_name, d_list in new_deps.items():
                for d in d_list:
                    if d not in new_deps:
                        return [f"ОШИБКА: неизвестная зависимость '{d}' в файле состояния"]

            self.deps = new_deps
            self.titles = new_titles
            self.status = new_status
            self.deadlines = new_deadlines
            return [f"Загружено задач: {len(self.deps)}"]

        return [f"ОШИБКА: неизвестная команда '{cmd}'"]


def load_tasks_file(path: str) -> Scheduler:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            raw_lines = f.readlines()
    except OSError as e:
        print(f"Ошибка: не удалось открыть файл '{path}': {e}", file=sys.stderr)
        sys.exit(1)

    sched = Scheduler()
    for line_no, raw_line in enumerate(raw_lines, 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = FILE_LINE_RE.match(raw_line)
        if not m:
            print(f"Ошибка: строка {line_no}: неверный синтаксис описания задачи", file=sys.stderr)
            sys.exit(1)

        name = m.group("name").strip()
        title = m.group("title")
        deps_raw = m.group("deps").strip()

        if not name:
            print(f"Ошибка: строка {line_no}: пустое имя задачи", file=sys.stderr)
            sys.exit(1)
        if name in sched.deps:
            print(f"Ошибка: строка {line_no}: дублирующаяся задача '{name}'", file=sys.stderr)
            sys.exit(1)

        dep_list: list[str] = []
        if deps_raw and deps_raw != "-":
            seen: set[str] = set()
            for part in deps_raw.split(","):
                d = part.strip()
                if not d or any(ch.isspace() for ch in d):
                    print(f"Ошибка: строка {line_no}: некорректный список зависимостей", file=sys.stderr)
                    sys.exit(1)
                if d not in seen:
                    seen.add(d)
                    dep_list.append(d)

        sched.deps[name] = dep_list
        sched.titles[name] = title
        sched.status[name] = "waiting"
        sched.deadlines[name] = None

    for t_name, d_list in sched.deps.items():
        for d in d_list:
            if d not in sched.deps:
                print(
                    f"Ошибка: задача '{t_name}' зависит от несуществующей задачи '{d}'",
                    file=sys.stderr,
                )
                sys.exit(1)

    return sched


def main() -> int:
    args = sys.argv[1:]
    if len(args) > 1:
        print("Ошибка: слишком много аргументов командной строки", file=sys.stderr)
        return 2

    if len(args) == 1:
        sched = load_tasks_file(args[0])
        cycle = sched.find_cycle()
        if cycle is not None:
            print("ОШИБКА: обнаружена циклическая зависимость!")
            print(f"Цепочка: {' → '.join(cycle)}")
            print("Невозможно определить порядок выполнения.")
            return 1
        print("\n".join(sched.format_plan()))
        return 0

    sched = Scheduler()
    text = sys.stdin.read()
    if text.startswith("\ufeff"):
        text = text[1:]

    out: list[str] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        out.extend(sched.execute_command(raw_line))

    if out:
        sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())