from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def normalize_member_value(value: Any) -> str:
    """Normalize a submitted Member value for counting and display.

    Numeric values such as 7, 7.0 and "7" become "7". Blank values are
    ignored. Non-numeric values are preserved as trimmed text.
    """
    if value in (None, ""):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    try:
        number = float(text.replace(",", ""))
        if number.is_integer():
            return str(int(number))
    except (TypeError, ValueError, OverflowError):
        pass

    return text


def most_frequent_member(rows: Iterable[Any], attribute: str = "member_no") -> str:
    """Return the Member value occurring most often in the supplied rows.

    The highest frequency wins. When two values have the same frequency, the
    value that appears first in the input rows wins. This keeps the result
    stable and prevents one-off incorrect values, such as a Telegram ID entered
    in the Member field, from appearing when the correct Member is repeated.
    """
    values: list[str] = []
    for row in rows:
        value = normalize_member_value(getattr(row, attribute, None))
        if value:
            values.append(value)

    if not values:
        return ""

    counts = Counter(values)
    highest = max(counts.values())
    return next(value for value in values if counts[value] == highest)
