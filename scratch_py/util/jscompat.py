"""JavaScript-compatible value coercion, matching scratch-vm's util/cast.js.

Every subtle rule here exists because Scratch runs on JavaScript doubles:
modulo sign follows the dividend, Math.round rounds half toward +infinity,
string equality is case-insensitive, and number formatting follows the ECMAScript
Number::toString algorithm. Getting these right is what makes projects behave
identically under this runtime.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal

_NAN = float("nan")
_INF = float("inf")

_DECIMAL_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_HEX_RE = re.compile(r"^([+-]?)0[xX]([0-9a-fA-F]+)$")
_INF_RE = re.compile(r"^([+-]?)Infinity$")


def _string_to_number(s: str) -> float:
    t = s.strip()
    if t == "":
        return 0.0
    m = _INF_RE.match(t)
    if m:
        return -_INF if m.group(1) == "-" else _INF
    m = _HEX_RE.match(t)
    if m:
        value = int(m.group(2), 16)
        if m.group(1) == "-":
            value = -value
        return float(value)
    if not _DECIMAL_RE.match(t):
        return _NAN
    return float(t)


def to_number(value) -> float | int:
    """Coerce a Scratch value to a number using JavaScript Number() rules."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return _string_to_number(value)
    if value is None:
        return 0.0
    return _string_to_number(to_string(value))


def num_or_nan(value) -> float:
    """Number coercion, but whitespace-only / non-numeric strings become NaN."""
    if isinstance(value, str):
        n = _string_to_number(value)
    elif isinstance(value, bool):
        n = 1.0 if value else 0.0
    elif isinstance(value, (int, float)):
        n = float(value)
    else:
        n = _NAN
    if math.isnan(n) and isinstance(value, (int, float)):
        return _NAN
    if isinstance(value, str) and value.strip() == "":
        return _NAN
    return n


def is_numeric(value) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return not (isinstance(value, float) and math.isnan(value))
    if isinstance(value, str):
        if value.strip() == "":
            return False
        return not math.isnan(_string_to_number(value))
    return False


def num_to_string(value: float | int) -> str:
    """Format a number the way JavaScript String(number) does."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    f = float(value)
    if math.isnan(f):
        return "NaN"
    if math.isinf(f):
        return "Infinity" if f > 0 else "-Infinity"
    if f == 0:
        return "0"
    sign, digits, exponent = Decimal(repr(f)).as_tuple()
    ds = "".join(str(d) for d in digits)
    k = exponent + len(ds)
    while len(ds) > 1 and ds.endswith("0"):
        ds = ds[:-1]
    neg = sign == 1
    out = _render_digits(ds, k)
    return "-" + out if neg else out


def _render_digits(ds: str, k: int) -> str:
    if -6 < k <= 21:
        if k >= len(ds):
            return ds + "0" * (k - len(ds))
        if k > 0:
            return ds[:k] + "." + ds[k:]
        return "0." + "0" * (-k) + ds
    exp = k - 1
    mantissa = ds[0] + ("." + ds[1:] if len(ds) > 1 else "")
    return f"{mantissa}e{'+' if exp >= 0 else '-'}{abs(exp)}"


def to_string(value) -> str:
    """Coerce a Scratch value to its display string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return num_to_string(value)
    if value is None:
        return ""
    return str(value)


def to_bool(value) -> bool:
    """Coerce a Scratch value to a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("", "0", "false")
    if isinstance(value, (int, float)):
        return value == value and value != 0
    return bool(value)


def compare(v1, v2) -> int:
    """The ( ) < ( ) comparison: numeric when both coerce, else alphabetic."""
    n1 = num_or_nan(v1)
    n2 = num_or_nan(v2)
    if math.isnan(n1) or math.isnan(n2):
        s1 = to_string(v1).lower()
        s2 = to_string(v2).lower()
        if s1 < s2:
            return -1
        if s1 > s2:
            return 1
        return 0
    if n1 < n2:
        return -1
    if n1 > n2:
        return 1
    return 0


def equals(v1, v2) -> bool:
    """The ( ) = ( ) block: numeric equality, else case-insensitive strings."""
    return compare(v1, v2) == 0


def js_mod(a, b) -> float:
    """JavaScript % operator: result takes the sign of the dividend."""
    x = float(to_number(a))
    y = float(to_number(b))
    if y == 0 or math.isnan(x) or math.isnan(y):
        return _NAN
    if math.isinf(x) and math.isinf(y):
        return _NAN
    return math.fmod(x, y)


def js_round(x) -> float:
    """JavaScript Math.round: half rounds toward +infinity."""
    v = float(to_number(x))
    if math.isnan(v) or math.isinf(v):
        return v
    return float(math.floor(v + 0.5))


def js_divide(a, b) -> float:
    x = float(to_number(a))
    y = float(to_number(b))
    if y == 0:
        if x == 0 or math.isnan(x):
            return _NAN
        return _INF if (x > 0) == (not _neg_zero(y)) else -_INF
    return x / y


def _neg_zero(v: float) -> bool:
    return v == 0 and math.copysign(1, v) < 0


def clamp_effect(value, lo=-100.0, hi=100.0) -> float:
    v = float(to_number(value))
    if math.isnan(v):
        return 0.0
    return max(lo, min(hi, v))


def math_op(op: str, value) -> float:
    x = float(to_number(value))
    if op == "abs":
        return abs(x)
    if op == "floor":
        return float(math.floor(x))
    if op == "ceiling":
        return float(math.ceil(x))
    if op == "sqrt":
        return math.sqrt(x) if x >= 0 else _NAN
    if op == "sin":
        return math.sin(math.radians(x))
    if op == "cos":
        return math.cos(math.radians(x))
    if op == "tan":
        a = math.radians(x)
        c = math.cos(a)
        return math.sin(a) / c if c != 0 else _INF
    if op == "asin":
        return math.degrees(math.asin(x)) if -1 <= x <= 1 else _NAN
    if op == "acos":
        return math.degrees(math.acos(x)) if -1 <= x <= 1 else _NAN
    if op == "atan":
        return math.degrees(math.atan(x))
    if op == "ln":
        return math.log(x) if x > 0 else _NAN
    if op == "log":
        return math.log10(x) if x > 0 else _NAN
    if op == "e ^":
        return math.exp(x)
    if op == "10 ^":
        return math.pow(10.0, x)
    return _NAN


def to_list_index(index, length: int) -> int | None:
    """Cast.toListIndex: 1-based whole number within range, else None."""
    if isinstance(index, str) and index.lower() in ("all", "last"):
        return None
    n = num_or_nan(index)
    if math.isnan(n):
        return None
    if float(n) != math.floor(n):
        return None
    if n < 1 or n > length:
        return None
    return int(n)


def letter_of(index, text) -> str:
    s = to_string(text)
    i = to_list_index(index, len(s))
    if i is None:
        return ""
    return s[i - 1]


def contains(text: str, sub: str) -> bool:
    return to_string(sub).lower() in to_string(text).lower()


def pick_random(a, b):
    import random

    n1 = num_or_nan(a)
    n2 = num_or_nan(b)
    if math.isnan(n1):
        n1 = 0.0
    if math.isnan(n2):
        n2 = 0.0
    low, high = min(n1, n2), max(n1, n2)
    if low == high:
        return low
    low_i = math.ceil(low)
    high_i = math.floor(high)
    if low_i <= high_i and abs(low_i - low) < 1e-9 and abs(high_i - high) < 1e-9:
        return random.randint(int(low_i), int(high_i))
    return random.uniform(low, high)


NAN = _NAN
INF = _INF
