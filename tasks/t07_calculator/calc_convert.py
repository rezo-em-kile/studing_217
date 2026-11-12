"""Конвертер величин: длина, масса, время, температура.

    convert 5 km to miles   →  3.10686 miles
Результат - не больше 6 значащих цифр (половина - от нуля), без лишних нулей.
"""
import math
import re
from decimal import ROUND_HALF_UP, Decimal, localcontext

NUMBER_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
SIGNIFICANT = 6

# единица -> (величина, множитель к базовой единице); множители точные из условия
UNITS = (
    (("m",), "длина", 1.0),
    (("km",), "длина", 1000.0),
    (("cm",), "длина", 0.01),
    (("mm",), "длина", 0.001),
    (("mi", "mile", "miles"), "длина", 1609.344),
    (("ft", "foot", "feet"), "длина", 0.3048),
    (("in", "inch", "inches"), "длина", 0.0254),
    (("yd", "yard", "yards"), "длина", 0.9144),
    (("kg",), "масса", 1.0),
    (("g",), "масса", 0.001),
    (("mg",), "масса", 1e-6),
    (("t", "ton", "tonne", "tonnes"), "масса", 1000.0),
    (("lb", "lbs", "pound", "pounds"), "масса", 0.45359237),
    (("oz", "ounce", "ounces"), "масса", 0.028349523125),
    (("s", "sec"), "время", 1.0),
    (("min",), "время", 60.0),
    (("h", "hr", "hour", "hours"), "время", 3600.0),
    (("day", "days"), "время", 86400.0),
    (("c", "°c", "celsius"), "температура", "C"),
    (("f", "°f", "fahrenheit"), "температура", "F"),
    (("k", "kelvin"), "температура", "K"),
)


class ConvertError(Exception):
    """Ошибка в команде convert."""


def find_unit(name):
    key = name.lower()
    for names, kind, factor in UNITS:
        if key in names:
            return kind, factor
    raise ConvertError(f"неизвестная единица измерения «{name}»")


def to_kelvin(value, scale):
    if scale == "C":
        return value + 273.15
    if scale == "F":
        return (value - 32) * 5 / 9 + 273.15
    return value


def from_kelvin(value, scale):
    if scale == "C":
        return value - 273.15
    if scale == "F":
        return (value - 273.15) * 9 / 5 + 32
    return value


def parse_value(text):
    if not NUMBER_RE.fullmatch(text):
        raise ConvertError(f"«{text}» - не число")
    value = float(text)
    if not math.isfinite(value):
        raise ConvertError(f"число «{text}» слишком большое")
    return value


def convert(value, source, target):
    source_kind, source_factor = find_unit(source)
    target_kind, target_factor = find_unit(target)
    if source_kind != target_kind:
        raise ConvertError(f"нельзя перевести {source} ({source_kind}) в {target} ({target_kind})")
    if source_kind == "температура":
        kelvin = to_kelvin(value, source_factor)
        if kelvin < 0:
            raise ConvertError(f"{value:g} {source} - ниже абсолютного нуля")
        return from_kelvin(kelvin, target_factor)
    result = value * source_factor / target_factor
    if not math.isfinite(result):
        raise ConvertError("результат слишком большой")
    return result


def format_value(value):
    """Не больше 6 значащих цифр: 3.10686, 1000, 123457000, 0, 1e-9, 2.5e+20."""
    if value == 0:
        return "0"
    with localcontext() as context:
        context.prec = 100
        context.rounding = ROUND_HALF_UP
        number = Decimal(repr(value))
        rounded = number.quantize(Decimal(1).scaleb(number.adjusted() - SIGNIFICANT + 1))
        if abs(value) >= 1e15 or abs(value) < 1e-6:
            exponent = rounded.adjusted()
            mantissa = format(rounded.scaleb(-exponent), "f")
            if "." in mantissa:
                mantissa = mantissa.rstrip("0").rstrip(".")
            return f"{mantissa}e{'-' if exponent < 0 else '+'}{abs(exponent)}"
        text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def run(arguments):
    """arguments - слова после convert: ЧИСЛО ЕДИНИЦА to|in ЕДИНИЦА. Возвращает «3.10686 miles»."""
    words = arguments.split()
    if len(words) != 4:
        raise ConvertError("формат: convert ЧИСЛО ЕДИНИЦА to ЕДИНИЦА (например, convert 5 km to miles)")
    value_text, source, connector, target = words
    if connector.lower() not in ("to", "in"):
        raise ConvertError(f"между единицами нужно «to» или «in», а не «{connector}»")
    value = parse_value(value_text)
    return f"{format_value(convert(value, source, target))} {target}"
