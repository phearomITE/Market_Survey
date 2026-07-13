from __future__ import annotations

from datetime import datetime, date
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
    "submitter_name": [
        "submitter_name", "enter_name", "name_submit", "Enter Name / ឈ្មោះអ្នក Submit",
        "1. OUTLET INFORMATION / Enter Name / ឈ្មោះអ្នក Submit",
        "1. OUTLET INFORMATION/Enter Name / ឈ្មោះអ្នក Submit",
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
        "issue_suggestion/key_issue_detail", "observation_group/key_issue_text",
        "issue_suggestion/key_issues_detail", "key_issues_group/key_issues_detail",
        "5. Key Issues and Initiative Idea / Suggestion / Key Issues Detail",
        "5. Key Issues and Initiative Idea / Suggestion/Key Issues Detail",
    ],
    "suggestion_text": [
        "initiative_idea_suggestion", "suggestion_text", "initiative_suggestion", "suggestion",
        "Suggestion Text", "Initiative Idea / Suggestion",
        "issue_suggestion/initiative_suggestion", "observation_group/suggestion_text",
        "issue_suggestion/initiative_idea_suggestion", "key_issues_group/initiative_idea_suggestion",
        "5. Key Issues and Initiative Idea / Suggestion / Initiative Idea / Suggestion",
        "5. Key Issues and Initiative Idea / Suggestion/Initiative Idea / Suggestion",
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
}


def flatten_dict(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in (data or {}).items():
        full_key = f"{prefix}/{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten_dict(value, full_key))
        else:
            out[full_key] = value
    return out


def _key_norm(key: str) -> str:
    return str(key).strip().lower().replace(" ", "_")


def _last_part(key: str) -> str:
    return _key_norm(str(key).split("/")[-1])


def get_any(row: dict, keys: list[str], default=None):
    flat = flatten_dict(row)
    for k in keys:
        if k in flat and flat[k] not in (None, ""):
            return flat[k]

    normalized = {_key_norm(k): k for k in flat.keys()}
    for k in keys:
        real_key = normalized.get(_key_norm(k))
        if real_key and flat.get(real_key) not in (None, ""):
            return flat.get(real_key)

    last_map = {_last_part(k): k for k in flat.keys()}
    for k in keys:
        real_key = last_map.get(_last_part(k))
        if real_key and flat.get(real_key) not in (None, ""):
            return flat.get(real_key)
    return default


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


def normalize_submission(row: dict) -> dict:
    flat = flatten_dict(row)
    sub_id = str(
        row.get("_id")
        or row.get("_uuid")
        or flat.get("meta/instanceID")
        or flat.get("instanceID")
        or row.get("id")
        or ""
    )
    submitted_at = parse_datetime(row.get("_submission_time") or row.get("submission_time") or row.get("end"))
    rdate = parse_date(get_any(row, ALIASES["report_date"])) or (submitted_at.date() if submitted_at else None)

    return {
        "submission_id": sub_id,
        "submission_time": submitted_at,
        "report_date": rdate,
        "region": normalize_region(get_any(row, ALIASES["region"])),
        "dealer": normalize_dealer(get_any(row, ALIASES["dealer"], "")),
        "group_no": to_int(get_any(row, ALIASES["group_no"])),
        "member_no": to_int(get_any(row, ALIASES["member_no"])),
        "total_outlet_visit_target": to_int(get_any(row, ALIASES["total_outlet_visit_target"])),
        "outlet_name": get_any(row, ALIASES["outlet_name"]),
        "outlet_type": normalize_outlet_type(get_any(row, ALIASES["outlet_type"])),
        "is_new_outlet": yes_value(get_any(row, ALIASES["is_new_outlet"])),
        "submitter_name": get_any(row, ALIASES["submitter_name"]),
        "phone_number": str(get_any(row, ALIASES["phone_number"], "") or "") or None,
        "location_text": get_any(row, ALIASES["location_text"]),
        "gps_text": str(get_any(row, ALIASES["gps_text"], "") or "") or None,
        "gps_latitude": to_float(get_any(row, ALIASES["gps_latitude"])),
        "gps_longitude": to_float(get_any(row, ALIASES["gps_longitude"])),
        "key_issue_text": get_any(row, ALIASES["key_issue_text"]),
        "suggestion_text": get_any(row, ALIASES["suggestion_text"]),
        "_flat": flat,  # transient only; sync.py converts it to SQL metric rows, not DB JSON.
    }
