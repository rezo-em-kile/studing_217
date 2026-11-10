import heapq
import re
import sys

# Максимальное время стоянки поезда на платформе, в минутах (2 часа)
MAXSTOYANKA = 120

# Одна строка расписания: «Название: прибытие ЧЧ:ММ, отправление ЧЧ:ММ»
STROKA = re.compile(r"^(.*?)\s*:\s*прибытие\s+([^\s,]+)\s*,\s*отправление\s+(\S+)$", re.IGNORECASE)
# Время: часы одной или двумя цифрами, минуты ровно двумя
VREMYA = re.compile(r"^([0-9]{1,2}):([0-9]{2})$")


def oshibka(tekst, kod=1):
    """Печатает сообщение об ошибке в stderr и завершает программу."""
    sys.stderr.write("Ошибка: " + tekst + "\n")
    sys.exit(kod)


def razobrat(tekst, nomer, chto, konec):
    """Разбирает время «ЧЧ:ММ». Для отправления (konec=True) допустимо 24:00."""
    sovpalo = VREMYA.match(tekst)
    if sovpalo is None:
        oshibka(f"строка {nomer}: некорректное время {chto} «{tekst}», нужен формат ЧЧ:ММ")
    chasy = int(sovpalo.group(1))
    minuty = int(sovpalo.group(2))
    if minuty > 59:
        oshibka(f"строка {nomer}: некорректное время {chto} «{tekst}», минут должно быть от 00 до 59")
    if konec and chasy == 24 and minuty == 0:
        return chasy, minuty
    if chasy > 23:
        oshibka(f"строка {nomer}: некорректное время {chto} «{tekst}», часов должно быть от 0 до 23")
    return chasy, minuty


# --- чтение данных (файл из аргумента или стандартный ввод) ---
argumenty = sys.argv[1:]
if len(argumenty) > 1:
    oshibka("слишком много аргументов, укажите один файл или передайте расписание через stdin", 2)

if argumenty:
    try:
        with open(argumenty[0], "rb") as fail:
            dannye = fail.read()
    except OSError as e:
        oshibka(f"не удалось открыть файл «{argumenty[0]}»: {e.strerror}")
else:
    dannye = sys.stdin.buffer.read()

try:
    tekst = dannye.decode("utf-8-sig")
except UnicodeDecodeError:
    oshibka("файл должен быть в кодировке UTF-8")

# --- разбор расписания ---
poezda = []      # (прибытие, отправление, название, прибытие текстом, отправление текстом)
nazvaniya = set()

for nomer, stroka in enumerate(tekst.split("\n"), 1):
    stroka = stroka.strip()
    if stroka == "" or stroka.startswith("#"):
        continue

    sovpalo = STROKA.match(stroka)
    if sovpalo is None:
        oshibka(f"строка {nomer}: не удалось разобрать «{stroka}», ожидается "
                f"«Название: прибытие ЧЧ:ММ, отправление ЧЧ:ММ»")

    imya = sovpalo.group(1).strip()
    if imya == "":
        oshibka(f"строка {nomer}: пустое название поезда")

    ch1, m1 = razobrat(sovpalo.group(2), nomer, "прибытия", False)
    ch2, m2 = razobrat(sovpalo.group(3), nomer, "отправления", True)

    if imya in nazvaniya:
        oshibka(f"строка {nomer}: поезд «{imya}» уже встречался в расписании")
    nazvaniya.add(imya)

    pribytie = ch1 * 60 + m1
    otpravlenie = ch2 * 60 + m2
    if otpravlenie < pribytie:      # отправление на следующие сутки
        otpravlenie = otpravlenie + 1440

    stoyanka = otpravlenie - pribytie
    if stoyanka == 0:
        oshibka(f"строка {nomer}: поезд «{imya}» прибывает и отправляется в одно время")
    if stoyanka > MAXSTOYANKA:
        oshibka(f"строка {nomer}: поезд «{imya}» стоит на платформе дольше 2 часов")

    poezda.append((pribytie, otpravlenie, imya, f"{ch1:02d}:{m1:02d}", f"{ch2:02d}:{m2:02d}"))

