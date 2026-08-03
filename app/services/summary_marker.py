from __future__ import annotations

import unicodedata
from typing import Any


FINAL_SUMMARY_KEYWORDS = (
    "បូកសរុបរួម",
    "បូកសរុបរូម",
    "សរុបរួម",
    "បួកសរុបរួម",
)


def _compact_marker(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return "".join(
        char
        for char in text
        if not unicodedata.category(char).startswith(("Z", "C", "P"))
    )


def is_final_summary_outlet_name(value: Any) -> bool:
    """Recognize the Khmer final-summary outlet marker safely.

    Kobo may preserve invisible controls or non-ASCII spaces that do not show
    in its table. Khmer combining marks are deliberately retained.
    """
    normalized = _compact_marker(value)
    if normalized in {_compact_marker(item) for item in FINAL_SUMMARY_KEYWORDS}:
        return True
    return (
        normalized.startswith(("បូកសរុប", "បួកសរុប"))
        and normalized.endswith(("រួម", "រូម"))
        and len(normalized) <= 14
    )
