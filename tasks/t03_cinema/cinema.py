import re
import sys

# Цена места по символу из файла зала
CENY = {"o": 300, "V": 600, "D": 300}
# Через сколько минут неоплаченная бронь истекает
OZHIDANIE = 10

MESTO = re.compile(r"^([0-9]+):([0-9]+)$")      # РЯД:МЕСТО
CHISLO = re.compile(r"^[0-9]+$")                 # номер брони
VREMYA = re.compile(r"^([0-9]{2}):([0-9]{2})$")  # ЧЧ:ММ


class Oshibka(Exception):
    """Ошибка в команде: печатается как «ОШИБКА: ...», работа продолжается."""


def zavershit(tekst, kod=1):
    """Ошибка запуска или файла зала: сообщение в stderr и выход."""
    sys.stderr.buffer.write(("Ошибка: " + tekst + "\n").encode("utf-8"))
    sys.exit(kod)


def vyvod(stroki):
    sys.stdout.buffer.write("".join(s + "\n" for s in stroki).encode("utf-8"))
    sys.stdout.buffer.flush()


def minuty(tekst):
    """«ЧЧ:ММ» -> минуты от начала суток."""
    sovpalo = VREMYA.match(tekst)
    if sovpalo is None:
        raise Oshibka(f"некорректное время «{tekst}», нужен формат ЧЧ:ММ")
    chasy = int(sovpalo.group(1))
    minut = int(sovpalo.group(2))
    if chasy > 23 or minut > 59:
        raise Oshibka(f"некорректное время «{tekst}», часы 00-23, минуты 00-59")
    return chasy * 60 + minut


def vremya(m):
    return f"{m // 60:02d}:{m % 60:02d}"


# ---------- запуск и файл зала ----------
if len(sys.argv) != 2:
    zavershit("укажите ровно один аргумент - файл зала: python cinema.py ЗАЛ.txt", 2)

try:
    with open(sys.argv[1], "rb") as fail:
        dannye = fail.read()
except OSError as e:
    zavershit(f"не удалось открыть файл «{sys.argv[1]}»: {e.strerror}")

try:
    tekst = dannye.decode("utf-8-sig")
except UnicodeDecodeError:
    zavershit("файл зала должен быть в кодировке UTF-8")

zal = []          # ряды зала: строки из символов o, V, D и «.»
for stroka in tekst.split("\n"):
    stroka = stroka.strip()
    if stroka == "":
        continue
    for nomermesta, simvol in enumerate(stroka, 1):
        if simvol not in "oVD.":
            zavershit(f"файл зала: ряд {len(zal) + 1}, место {nomermesta}: недопустимый символ «{simvol}»")
    zal.append(stroka)

VSEGO = sum(len(ryad) - ryad.count(".") for ryad in zal)
if VSEGO == 0:
    zavershit("в файле зала нет ни одного места")


# ---------- состояние ----------
teper = 0        # часы программы, минуты от 00:00
seansy = {}      # название сеанса -> {"nachalo": минуты или None, "broni": [...]}
broni = {}       # номер брони -> бронь
posledny = 0     # номер последней созданной брони


def nayti(imya):
    if imya not in seansy:
        raise Oshibka(f"сеанса «{imya}» нет")
    return seansy[imya]


def sostoyanie(b):
    """aktivno, oplacheno, otmeneno или istekla (неоплаченная бронь через 10 минут)."""
    if b["status"] == "aktivno" and teper >= b["vremya"] + OZHIDANIE:
        return "istekla"
    return b["status"]


def zanyatye(seans):
    """Множество занятых мест сеанса: оплаченные и ещё не истёкшие активные брони."""
    rezultat = set()
    for b in seans["broni"]:
        if sostoyanie(b) in ("aktivno", "oplacheno"):
            rezultat.add((b["ryad"], b["mesto"]))
    return rezultat


# ---------- команды ----------
for syroe in sys.stdin.buffer:
    stroka = syroe.decode("utf-8", errors="replace").strip()
    if stroka == "":
        continue
    komanda = stroka.split(None, 1)[0]
    otvet = []
    try:
        if komanda == "time":
            chasti = stroka.split()
            if len(chasti) != 2:
                raise Oshibka("ожидается: time ЧЧ:ММ")
            novoe = minuty(chasti[1])
            if novoe < teper:
                raise Oshibka(f"время нельзя вернуть назад (сейчас {vremya(teper)})")
            teper = novoe
            otvet.append(f"Время: {vremya(teper)}")

        elif komanda == "session":
            chasti = stroka.split()
            if len(chasti) < 2 or len(chasti) > 3:
                raise Oshibka("ожидается: session ИМЯ [ЧЧ:ММ]")
            imya = chasti[1]
            nachalo = None
            if len(chasti) == 3:
                nachalo = minuty(chasti[2])
            if imya in seansy:
                raise Oshibka(f"сеанс {imya} уже существует")
            seansy[imya] = {"nachalo": nachalo, "broni": []}
            if nachalo is None:
                otvet.append(f"Сеанс {imya} добавлен")
            else:
                otvet.append(f"Сеанс {imya} добавлен (начало в {vremya(nachalo)})")

        elif komanda == "book":
            chasti = stroka.split(None, 3)
            if len(chasti) < 3:
                raise Oshibka("ожидается: book СЕАНС РЯД:МЕСТО[,РЯД:МЕСТО...] ИМЯ")
            imyaseansa = chasti[1]
            seans = nayti(imyaseansa)
            if len(chasti) < 4:
                raise Oshibka("не указано имя пользователя")
            polzovatel = chasti[3]
            if seans["nachalo"] is not None and teper >= seans["nachalo"]:
                raise Oshibka(f"сеанс {imyaseansa} уже начался в {vremya(seans['nachalo'])}")

            mesta = []
            for kusok in chasti[2].split(","):
                sovpalo = MESTO.match(kusok)
                if sovpalo is None:
                    raise Oshibka(f"неверное место «{kusok}», нужен формат РЯД:МЕСТО")
                mesta.append((int(sovpalo.group(1)), int(sovpalo.group(2))))

            # групповая бронь - всё или ничего: сначала проверяем все места
            zanyato = zanyatye(seans)
            uzhe = set()
            for ryad, mesto in mesta:
                if ryad < 1 or ryad > len(zal) or mesto < 1 or mesto > len(zal[ryad - 1]) or zal[ryad - 1][mesto - 1] == ".":
                    raise Oshibka(f"ряд {ryad}, место {mesto} не существует")
                if (ryad, mesto) in uzhe:
                    raise Oshibka(f"ряд {ryad}, место {mesto} указано дважды")
                uzhe.add((ryad, mesto))
                if (ryad, mesto) in zanyato:
                    raise Oshibka(f"ряд {ryad}, место {mesto} уже забронировано")

            for ryad, mesto in mesta:
                posledny = posledny + 1
                b = {"nomer": posledny, "imya": polzovatel, "seans": imyaseansa, "ryad": ryad, "mesto": mesto,
                     "vremya": teper, "status": "aktivno", "otmena": 0}
                seans["broni"].append(b)
                broni[posledny] = b
                cena = CENY[zal[ryad - 1][mesto - 1]]
                otvet.append(f"Бронь {posledny}: {polzovatel}, сеанс {imyaseansa}, ряд {ryad}, место {mesto}, {cena} руб. - УСПЕШНО")

        elif komanda == "pay" or komanda == "cancel":
            chasti = stroka.split(None, 2)
            if len(chasti) < 3 or CHISLO.match(chasti[1]) is None:
                raise Oshibka(f"ожидается: {komanda} НОМЕР ИМЯ")
            nomer = int(chasti[1])
            if nomer not in broni:
                raise Oshibka(f"брони {nomer} нет")
            b = broni[nomer]
            if b["imya"] != chasti[2]:
                raise Oshibka(f"бронь {nomer} оформлена на другого пользователя")
            sost = sostoyanie(b)
            if komanda == "pay":
                if sost == "istekla":
                    raise Oshibka(f"бронь {nomer} истекла, оплатить нельзя")
                if sost == "otmeneno":
                    raise Oshibka(f"бронь {nomer} отменена, оплатить нельзя")
                if sost == "oplacheno":
                    raise Oshibka(f"бронь {nomer} уже оплачена")
                b["status"] = "oplacheno"
                otvet.append(f"Бронь {nomer} оплачена")
            else:
                if sost == "istekla":
                    raise Oshibka(f"бронь {nomer} уже истекла")
                if sost == "otmeneno":
                    raise Oshibka(f"бронь {nomer} уже отменена")
                b["status"] = "otmeneno"
                b["otmena"] = teper
                otvet.append(f"Бронь {nomer} отменена")

        elif komanda == "show" or komanda == "free" or komanda == "history":
            chasti = stroka.split()
            if len(chasti) != 2:
                raise Oshibka(f"ожидается: {komanda} СЕАНС")
            seans = nayti(chasti[1])
            zanyato = zanyatye(seans)

            if komanda == "free":
                otvet.append(f"Свободно мест: {VSEGO - len(zanyato)} из {VSEGO}")

            elif komanda == "show":
                shirina = max(len(ryad) for ryad in zal)
                dlina = len(f"Ряд {len(zal)}: ")
                otvet.append((" " * dlina + "".join(str(i).ljust(3) for i in range(1, shirina + 1))).rstrip())
                for nomerryada, ryad in enumerate(zal, 1):
                    s = f"Ряд {nomerryada}: ".ljust(dlina)
                    for nomermesta, simvol in enumerate(ryad, 1):
                        if simvol == ".":
                            simvol = " "
                        elif (nomerryada, nomermesta) in zanyato:
                            simvol = "x"
                        s = s + simvol.ljust(3)
                    otvet.append(s.rstrip())

            else:
                if len(seans["broni"]) == 0:
                    otvet.append("История пуста")
                for b in seans["broni"]:
                    sost = sostoyanie(b)
                    if sost == "aktivno":
                        podpis = "активно"
                    elif sost == "oplacheno":
                        podpis = "оплачено"
                    elif sost == "otmeneno":
                        podpis = f"отменено в {vremya(b['otmena'])}"
                    else:
                        podpis = f"истекло в {vremya(b['vremya'] + OZHIDANIE)}"
                    otvet.append(f"  {vremya(b['vremya'])} {b['imya']} → ряд {b['ryad']}, место {b['mesto']} ({podpis})")

        else:
            raise Oshibka(f"неизвестная команда «{komanda}»")

    except Oshibka as e:
        otvet = [f"ОШИБКА: {e}"]

    vyvod(otvet)
