from __future__ import annotations

from datetime import datetime, date
from functools import lru_cache
from typing import Any


ALIASES = {
    "dealer": [
        "dealer", "Dealer", "dealer_code", "select_dealer", "report_info/dealer",
        "outlet_info/dealer", "1. Report / Outlet Visit Information / Dealer",
        "1. OUTLET INFORMATION / Dealer", "1. OUTLET INFORMATION/Dealer",
    ],
    "region": [
        "region", "Region", "select_region", "report_info/region", "outlet_info/region",
        "1. Report / Outlet Visit Information / Region",
        "1. OUTLET INFORMATION / Region", "1. OUTLET INFORMATION/Region",
    ],
    "group_no": [
        "group", "group_no", "Group", "Group No", "report_info/group_no", "outlet_info/group_no",
        "1. Report / Outlet Visit Information / Group No",
        "1. OUTLET INFORMATION / Group", "1. OUTLET INFORMATION/Group",
    ],
    "member_no": [
        "member", "member_no", "Member", "Member No", "report_info/member_no", "outlet_info/member_no",
        "1. Report / Outlet Visit Information / Member No",
        "1. OUTLET INFORMATION / Member", "1. OUTLET INFORMATION/Member",
    ],
    "total_outlet_visit_target": [
        "total_outlet_visit_target", "Total Outlet Visit Target", "target_outlet_visit",
        "1. OUTLET INFORMATION / Total Outlet Visit Target",
        "1. OUTLET INFORMATION/Total Outlet Visit Target",
    ],
    "outlet_name": [
        "outlet_name", "Outlet_Name", "outlet", "Outlet", "report_info/outlet_name", "outlet_info/outlet_name",
        "1. Report / Outlet Visit Information / Outlet Name",
        "1. OUTLET INFORMATION / Outlet Name", "1. OUTLET INFORMATION/Outlet Name",
    ],
    "outlet_type": [
        "outlet_type", "Outlet_Type", "type_outlet", "report_info/outlet_type", "outlet_info/outlet_type",
        "1. Report / Outlet Visit Information / Outlet Type",
        "1. OUTLET INFORMATION / Outlet Type", "1. OUTLET INFORMATION/Outlet Type",
    ],
    "report_type": [
        "final_summary_report_type", "summary_report_type", "report_type",
        "outlet_info/final_summary_report_type",
        "1. OUTLET INFORMATION / Final Summary Report Type",
        "1. OUTLET INFORMATION/Final Summary Report Type",
    ],
    "submitter_name": [
        "submitter_name", "enter_name", "name_submit", "Enter Name / ឈ្មោះអ្នក Submit",
        "ចំណុចដួល",
        "1. OUTLET INFORMATION / Enter Name / ឈ្មោះអ្នក Submit",
        "1. OUTLET INFORMATION/Enter Name / ឈ្មោះអ្នក Submit",
        "1. OUTLET INFORMATION / ចំណុចដួល",
        "1. OUTLET INFORMATION/ចំណុចដួល",
    ],
    "phone_number": [
        "phone_number", "phone", "Phone Number",
        "1. OUTLET INFORMATION / Phone Number", "1. OUTLET INFORMATION/Phone Number",
    ],
    "location_text": [
        "location_of_visit_text", "location_text", "location_of_visit", "village", "commune",
        "report_info/location_text", "outlet_info/location_of_visit_text", "Location of Visit",
        "1. Report / Outlet Visit Information / Location of Visit Text",
        "1. OUTLET INFORMATION / Location of Visit Text", "1. OUTLET INFORMATION/Location of Visit Text",
    ],
    "gps_text": [
        "gps_location", "GPS Location = Location of Visit", "GPS Location / Location of Visit",
        "1. OUTLET INFORMATION / GPS Location = Location of Visit",
        "1. OUTLET INFORMATION/GPS Location = Location of Visit",
    ],
    "gps_latitude": [
        "_GPS Location = Location of Visit_latitude", "gps_latitude", "GPS Latitude",
        "1. OUTLET INFORMATION / GPS Latitude", "1. OUTLET INFORMATION/GPS Latitude",
    ],
    "gps_longitude": [
        "_GPS Location = Location of Visit_longitude", "gps_longitude", "GPS Longitude",
        "1. OUTLET INFORMATION / GPS Longitude", "1. OUTLET INFORMATION/GPS Longitude",
    ],
    "is_new_outlet": [
        "is_new_outlet", "Is New Outlet?", "new_outlet",
        "1. OUTLET INFORMATION / Is New Outlet?", "1. OUTLET INFORMATION/Is New Outlet?",
    ],
    "key_issue_text": [
        "key_issues_detail", "key_issue_text", "key_issue_detail", "key_issues", "key_issue",
        "Key Issue Text", "Key Issues", "Key Issues Detail",
        "បញ្ហាទីផ្សារ",
        "issue_suggestion/key_issue_detail", "observation_group/key_issue_text",
        "issue_suggestion/key_issues_detail", "key_issues_group/key_issues_detail",
        "5. Key Issues and Initiative Idea / Suggestion / Key Issues Detail",
        "5. Key Issues and Initiative Idea / Suggestion/Key Issues Detail",
        "3. FINAL បញ្ហាទីផ្សារ & បញ្ហាត្រូវដោះស្រាយ / បញ្ហាទីផ្សារ",
        "3. FINAL បញ្ហាទីផ្សារ & បញ្ហាត្រូវដោះស្រាយ/បញ្ហាទីផ្សារ",
    ],
    "suggestion_text": [
        "initiative_idea_suggestion", "suggestion_text", "initiative_suggestion", "suggestion",
        "Suggestion Text", "Initiative Idea / Suggestion",
        "បញ្ហាត្រូវដោះស្រាយ",
        "issue_suggestion/initiative_suggestion", "observation_group/suggestion_text",
        "issue_suggestion/initiative_idea_suggestion", "key_issues_group/initiative_idea_suggestion",
        "5. Key Issues and Initiative Idea / Suggestion / Initiative Idea / Suggestion",
        "5. Key Issues and Initiative Idea / Suggestion/Initiative Idea / Suggestion",
        "3. FINAL បញ្ហាទីផ្សារ & បញ្ហាត្រូវដោះស្រាយ / បញ្ហាត្រូវដោះស្រាយ",
        "3. FINAL បញ្ហាទីផ្សារ & បញ្ហាត្រូវដោះស្រាយ/បញ្ហាត្រូវដោះស្រាយ",
    ],
    "report_date": [
        "report_date", "survey_date", "date", "today", "report_info/report_date", "outlet_info/report_date",
        "1. Report / Outlet Visit Information / Report Date",
        "1. OUTLET INFORMATION / Report Date", "1. OUTLET INFORMATION/Report Date",
    ],
}


REGION_LABELS = {f"r{i}": f"R{i}" for i in range(1, 9)}

OUTLET_TYPE_LABELS = {
    # General trade
    "wholesale": "Wholesale",
    "drink_shop": "Drink Shop",
    "drink shop": "Drink Shop",
    "wet_market": "Wet Market",
    "wet market": "Wet Market",
    "trolley": "Trolley",

    # Channel Specialist
    "local_eat": "Local Eat",
    "local eat": "Local Eat",
    "coffee_bakery": "Coffee,Bakery",
    "coffee, bakery": "Coffee,Bakery",
    "coffee bakery": "Coffee,Bakery",
    "coffee,bakery": "Coffee,Bakery",
    "canteen": "Canteen",
    "sport_club": "Sport Club",
    "sport club": "Sport Club",
    "motor_shop": "Motor Shop",
    "motor shop": "Motor Shop",
    "local_drink": "Local Drink",
    "local drink": "Local Drink",
}


def normalize_report_type(value: Any) -> str | None:
    if value in (None, ""):
        return None
    value = str(value).strip().lower().replace("_", " ")
    if value in {"gt", "general", "general trade"}:
        return "GT"
    if value in {"horeca", "channel", "channel specialist", "specialist", "cs"}:
        return "HORECA"
    return str(value).strip().upper()


class FlatFieldMap(dict[str, Any]):
    """Flattened Kobo row with indexes built once per submission.

    A single survey row is queried hundreds of times while product metrics are
    created.  The previous code rebuilt three dictionaries on every lookup,
    which made a 1,600-row date take minutes.  This class preserves normal dict
    behaviour while reusing its exact/case/label indexes.
    """

    __slots__ = ("_lower", "_full_norm", "_leaf", "_strong")

    def __init__(self, values: dict[str, Any] | None = None):
        super().__init__(values or {})
        self._lower = {str(key).strip().lower(): key for key in self}
        self._full_norm = {_key_norm(key): key for key in self}
        self._leaf = {_last_part(key): key for key in self}
        self._strong = {
            "".join(
                char
                for char in str(key).strip().lower().split("/")[-1]
                if char.isalnum()
            ): key
            for key in self
        }

    @staticmethod
    def _non_empty(value: Any) -> bool:
        return value not in (None, "")

    def parser_value(self, keys: list[str], default=None):
        exact, full_norm, leaf = _compiled_parser_keys(tuple(keys))
        for key in exact:
            if key in self and self._non_empty(self[key]):
                return self[key]
        for normalized in full_norm:
            real_key = self._full_norm.get(normalized)
            if real_key is not None and self._non_empty(self.get(real_key)):
                return self.get(real_key)
        for normalized in leaf:
            real_key = self._leaf.get(normalized)
            if real_key is not None and self._non_empty(self.get(real_key)):
                return self.get(real_key)
        return default

    def first_value(self, keys: list[str]):
        """Fast equivalent of reports.aggregator.first_value()."""
        exact, lower, strong, leaf = _compiled_first_keys(tuple(keys))
        for key in exact:
            if key in self and self._non_empty(self[key]):
                return self[key]
        for normalized in lower:
            real_key = self._lower.get(normalized)
            if real_key is not None and self._non_empty(self.get(real_key)):
                return self.get(real_key)
        for normalized in strong:
            real_key = self._strong.get(normalized)
            if real_key is not None and self._non_empty(self.get(real_key)):
                return self.get(real_key)
        for normalized in leaf:
            real_key = self._leaf.get(normalized)
            if real_key is not None and self._non_empty(self.get(real_key)):
                return self.get(real_key)
        return None


def flatten_dict(data: dict[str, Any], prefix: str = "") -> FlatFieldMap:
    out: dict[str, Any] = {}

    def visit(values: dict[str, Any], current_prefix: str) -> None:
        for key, value in (values or {}).items():
            full_key = f"{current_prefix}/{key}" if current_prefix else str(key)
            if isinstance(value, dict):
                visit(value, full_key)
            else:
                out[full_key] = value

    visit(data or {}, prefix)
    return FlatFieldMap(out)


def _key_norm(key: str) -> str:
    return str(key).strip().lower().replace(" ", "_")


def _last_part(key: str) -> str:
    return _key_norm(str(key).split("/")[-1])


@lru_cache(maxsize=4096)
def _compiled_parser_keys(keys: tuple[str, ...]):
    """Compile aliases once instead of once per field per submission."""
    return (
        keys,
        tuple(_key_norm(key) for key in keys),
        tuple(_last_part(key) for key in keys),
    )


@lru_cache(maxsize=4096)
def _compiled_first_keys(keys: tuple[str, ...]):
    return (
        keys,
        tuple(str(key).strip().lower() for key in keys),
        tuple(
            "".join(
                char
                for char in str(key).strip().lower().split("/")[-1]
                if char.isalnum()
            )
            for key in keys
        ),
        tuple(_last_part(key) for key in keys),
    )


def get_any(row: dict, keys: list[str], default=None):
    flat = row if isinstance(row, FlatFieldMap) else flatten_dict(row)
    return flat.parser_value(keys, default)


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    s = str(value).strip().replace("Z", "")[:19]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%b %d, %Y", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).strip().replace("Z", "")[:19]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%b %d, %Y %I:%M %p"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def normalize_region(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    return REGION_LABELS.get(s.lower(), s.upper() if s.lower().startswith("r") else s)


def normalize_dealer(value: Any) -> str:
    if not value:
        return ""
    return str(value).strip().upper()


def normalize_outlet_type(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    s = raw.lower().replace("_", " ")
    if raw.lower() in OUTLET_TYPE_LABELS:
        return OUTLET_TYPE_LABELS[raw.lower()]
    # Channel Specialist outlet types first, because they also contain words like shop.
    if "local" in s and "eat" in s:
        return "Local Eat"
    if "coffee" in s or "bakery" in s:
        return "Coffee,Bakery"
    if "canteen" in s:
        return "Canteen"
    if "sport" in s and "club" in s:
        return "Sport Club"
    if "motor" in s and "shop" in s:
        return "Motor Shop"

    if "wholesale" in s or "ដុំ" in s:
        return "Wholesale"
    if "drink" in s or "shop" in s or "ហាង" in s:
        return "Drink Shop"
    if "wet" in s or "market" in s or "ផ្សារ" in s:
        return "Wet Market"
    if "trolley" in s or "រទេះ" in s:
        return "Trolley"
    return raw


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(str(value).replace(",", "").strip())))
    except Exception:
        return None


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def yes_value(value: Any) -> bool:
    if value in (None, ""):
        return False
    s = str(value).strip().lower()
    return s in {"1", "yes", "y", "true", "new", "ថ្មី", "មាន", "មានលក់", "លក់ដាច់", "sale", "fast_sale"}


def normalize_submission(
    row: dict,
    *,
    flat: FlatFieldMap | None = None,
) -> dict:
    """Normalize a Kobo submission using one shared flattened/indexed row."""
    flat = flat if isinstance(flat, FlatFieldMap) else flatten_dict(row)
    sub_id = str(
        row.get("_id")
        or row.get("_uuid")
        or flat.get("meta/instanceID")
        or flat.get("instanceID")
        or row.get("id")
        or ""
    )
    submitted_at = parse_datetime(row.get("_submission_time") or row.get("submission_time") or row.get("end"))
    value = flat.parser_value
    rdate = parse_date(value(ALIASES["report_date"])) or (submitted_at.date() if submitted_at else None)

    return {
        "submission_id": sub_id,
        "submission_time": submitted_at,
        "report_date": rdate,
        "region": normalize_region(value(ALIASES["region"])),
        "dealer": normalize_dealer(value(ALIASES["dealer"], "")),
        "group_no": to_int(value(ALIASES["group_no"])),
        "member_no": to_int(value(ALIASES["member_no"])),
        "total_outlet_visit_target": to_int(value(ALIASES["total_outlet_visit_target"])),
        "outlet_name": value(ALIASES["outlet_name"]),
        "outlet_type": normalize_outlet_type(value(ALIASES["outlet_type"])),
        "report_type": normalize_report_type(value(ALIASES["report_type"])),
        "is_new_outlet": yes_value(value(ALIASES["is_new_outlet"])),
        "submitter_name": value(ALIASES["submitter_name"]),
        "phone_number": str(value(ALIASES["phone_number"], "") or "") or None,
        "location_text": value(ALIASES["location_text"]),
        "gps_text": str(value(ALIASES["gps_text"], "") or "") or None,
        "gps_latitude": to_float(value(ALIASES["gps_latitude"])),
        "gps_longitude": to_float(value(ALIASES["gps_longitude"])),
        "key_issue_text": value(ALIASES["key_issue_text"]),
        "suggestion_text": value(ALIASES["suggestion_text"]),
        "_flat": flat,  # transient only; sync.py converts it to SQL metric rows, not DB JSON.
    }
