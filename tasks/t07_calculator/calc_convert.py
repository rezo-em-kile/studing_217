import math
import re
from decimal import Decimal, ROUND_HALF_UP

CONVERT_RE = re.compile(r"^convert\s+(\S+)\s+(\S+)\s+(?:to|in)\s+(\S+)$", re.IGNORECASE)
NUM_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")

UNIT_ALIASES: dict[str, tuple[str, str, float]] = {
    # Длина (базовая единица: m)
    "m": ("length", "m", 1.0),
    "km": ("length", "km", 1000.0),
    "cm": ("length", "cm", 0.01),
    "mm": ("length", "mm", 0.001),
    "mi": ("length", "mi", 1609.344),
    "mile": ("length", "mi", 1609.344),
    "miles": ("length", "mi", 1609.344),
    "ft": ("length", "ft", 0.3048),
    "foot": ("length", "ft", 0.3048),
    "feet": ("length", "ft", 0.3048),
    "in": ("length", "in", 0.0254),
    "inch": ("length", "in", 0.0254),
    "inches": ("length", "in", 0.0254),
    "yd": ("length", "yd", 0.9144),
    "yard": ("length", "yd", 0.9144),
    "yards": ("length", "yd", 0.9144),

    # Масса (базовая единица: kg)
    "kg": ("mass", "kg", 1.0),
    "g": ("mass", "g", 0.001),
    "mg": ("mass", "mg", 1e-6),
    "t": ("mass", "t", 1000.0),
    "ton": ("mass", "t", 1000.0),
    "tonne": ("mass", "t", 1000.0),
    "tonnes": ("mass", "t", 1000.0),
    "lb": ("mass", "lb", 0.45359237),
    "lbs": ("mass", "lb", 0.45359237),
    "pound": ("mass", "lb", 0.45359237),
    "pounds": ("mass", "lb", 0.45359237),
    "oz": ("mass", "oz", 0.028349523125),
    "ounce": ("mass", "oz", 0.028349523125),
    "ounces": ("mass", "oz", 0.028349523125),

    # Время (базовая единица: s)
    "s": ("time", "s", 1.0),
    "sec": ("time", "s", 1.0),
    "min": ("time", "min", 60.0),
    "h": ("time", "h", 3600.0),
    "hr": ("time", "h", 3600.0),
    "hour": ("time", "h", 3600.0),
    "hours": ("time", "h", 3600.0),
    "day": ("time", "day", 86400.0),
    "days": ("time", "day", 86400.0),

    # Температура
    "c": ("temp", "C", 1.0),
    "°c": ("temp", "C", 1.0),
    "celsius": ("temp", "C", 1.0),
    "f": ("temp", "F", 1.0),
    "°f": ("temp", "F", 1.0),
    "fahrenheit": ("temp", "F", 1.0),
    "k": ("temp", "K", 1.0),
    "kelvin": ("temp", "K", 1.0),
}


class ConvertError(Exception):
    pass


def format_significant_6(val: float) -> str:
    if val == 0.0:
        return "0"

    d = Decimal(str(val))
    sign = "-" if d < 0 else ""
    d_abs = abs(d)
    exp = d_abs.adjusted()

    # Округляем до 6 значащих цифр (половина - от нуля)
    shift = 5 - exp
    q = Decimal(f"1e{-shift}") if shift >= 0 else Decimal(f"1e{-shift}")
    rounded = d_abs.quantize(q, rounding=ROUND_HALF_UP)

    if rounded == 0:
        return "0"

    new_exp = rounded.adjusted()
    if new_exp >= 15 or new_exp < -6:
        mantissa = rounded.scaleb(-new_exp)
        m_str = format(mantissa, "f")
        if "." in m_str:
            m_str = m_str.rstrip("0").rstrip(".")
        e_sign = "+" if new_exp >= 0 else "-"
        return f"{sign}{m_str}e{e_sign}{abs(new_exp)}"

    s = format(rounded, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return f"{sign}{s}"


def convert_command(line: str) -> str:
    m = CONVERT_RE.match(line.strip())
    if not m:
        raise ConvertError("неверный синтаксис convert (ожидалось: convert <число> <из> to|in <в>)")

    raw_val, raw_src, raw_dst = m.group(1), m.group(2), m.group(3)
    if not NUM_RE.match(raw_val):
        raise ConvertError(f"некорректное число '{raw_val}'")

    val = float(raw_val)
    if math.isnan(val) or math.isinf(val):
        raise ConvertError("некорректное числовое значение")

    src_info = UNIT_ALIASES.get(raw_src.lower())
    dst_info = UNIT_ALIASES.get(raw_dst.lower())
    if src_info is None:
        raise ConvertError(f"неизвестная единица измерения '{raw_src}'")
    if dst_info is None:
        raise ConvertError(f"неизвестная единица измерения '{raw_dst}'")

    src_cat, src_canon, src_factor = src_info
    dst_cat, dst_canon, dst_factor = dst_info

    if src_cat != dst_cat:
        raise ConvertError(f"несовместимые величины: '{raw_src}' и '{raw_dst}'")

    if src_cat == "temp":
        if src_canon == "C":
            kelvin = val + 273.15
        elif src_canon == "F":
            kelvin = (val - 32.0) * 5.0 / 9.0 + 273.15
        else:
            kelvin = val

        if kelvin < -1e-9:
            raise ConvertError("температура ниже абсолютного нуля")
        if abs(kelvin) < 1e-12:
            kelvin = 0.0

        if dst_canon == "C":
            res = kelvin - 273.15
        elif dst_canon == "F":
            res = (kelvin - 273.15) * 9.0 / 5.0 + 32.0
        else:
            res = kelvin
    else:
        res = val * src_factor / dst_factor

    if abs(res) < 1e-15:
        res = 0.0

    formatted = format_significant_6(res)
    return f"= {formatted} {raw_dst}"