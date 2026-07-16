# app/reports/aggregator.py

from __future__ import annotations

from collections import Counter
from datetime import datetime
import difflib
import re
from typing import Any

from sqlalchemy import text

from app.db.database import SessionLocal

OWN_PRODUCTS = [
    "CB LITE ORD",
    "CBC 4.4 NCP",
    "CB Original NCP",
    "CB LITE NCP",
    "CB BLACK NCP",
    "CAMBODIA COLA",
    "WURKZ",
    "CAMBODIA ED",
    "DAZZ",
    "DAZZ Zero Sugar",
    "IZE PET 300ml Flavour",
    "IZE COLA PET 1.5L All SKUs",
    "EXPREZ Melon",
    "Wurkz Ice",
    "CAMBODIA Sport 300mL",
    "CAMBODIA Sport 500mL",
    "CAMBODIA WATER 500mL",
    "CAMBODIA WATER 1500mL",
]


# Kobo own-product field policy.
#
# The form keeps legacy question names hidden for backward compatibility, while
# the sync and report layers enforce the same business rule so historical values
# from removed fields cannot reappear in a newly generated report.
DEFAULT_OWN_PRODUCT_FIELDS = frozenset({"status", "mov"})
OWN_PRODUCT_FIELD_POLICY = {
    "CB LITE ORD": frozenset({"status", "mov", "stock", "bbe", "buy_in", "sell_out"}),
    "CBC 4.4 NCP": frozenset(
        {"status", "mov", "stock", "bbe", "buy_in", "sell_out", "ring_pull"}
    ),
    "CB Original NCP": frozenset(
        {"status", "mov", "stock", "bbe", "buy_in", "sell_out", "ring_pull"}
    ),
    "CB LITE NCP": frozenset(
        {"status", "mov", "stock", "bbe", "buy_in", "sell_out", "ring_pull"}
    ),
    "CAMBODIA ED": frozenset({"status", "mov", "stock"}),
}


def own_product_field_enabled(product: str, field: str) -> bool:
    """Return whether an own-product field is active in the current Kobo form."""
    return field in OWN_PRODUCT_FIELD_POLICY.get(product, DEFAULT_OWN_PRODUCT_FIELDS)


COMPETITOR_PRODUCTS = [
    "GB SNOW ORD",
    "HANUMAN LITE ORD",
    "Krud LITE ORD",
    "CB Original NCP",
    "GB Original NCP",
    "Krud NCP",
    "GB SNOW NCP",
    "Hanuman LITE NCP",
    "Krud LITE NCP",
    "Greet LITE NCP",
    "Hanuman Black NCP",
    "Coca Cola 330ml",
    "Boostrong",
    "Krud ED",
    "Champion",
    "King Kong Ice",
    "Krud Ice",
    "Super Boostrong",
    "King Kong",
    "AIRA",
    "BACCHUSE",
    "Dragon",
    "BACCHUSE Sugar Free",
    "POP Z Flavour",
    "V Cola 350ml",
    "Coca 1.5L",
    "Big Cola 3L",
    "EXPREZ Can 330ml",
    "Sting Can 330ml",
    "Idol Can 330ml",
    "CAMBODIA Sport 300ml",
    "Pocari Sweat",
    "V-Active Sport",
    "Vital 500mL",
    "Provida 500mL",
    "Ganzberg 500ml",
    "Hitech 500mL",
    "Vital 1500mL",
    "Provida 1500mL",
    "Ganzberg 1500ml",
    "Hitech 1500mL",
]

RING_PRODUCTS = ["CBL NCP 6 Can", "CBL NCP 5 USD"]
RING_PRODUCT_ALIASES = {
    "CBL NCP 6 Can": ["CBL NCP 6 Can", "CBC, CBL Can and CBB Can"],
    "CBL NCP 5 USD": ["CBL NCP 5 USD", "Wurkz NCP 5 USD"],
}

OFFTAKE_COMPARE_GROUPS = [
    ["CB LITE ORD", "GB SNOW ORD", "HANUMAN LITE ORD", "Krud LITE ORD"],
    ["CBC 4.4 NCP", "CB Original NCP", "GB Original NCP", "Krud NCP"],
    ["CB LITE NCP", "GB SNOW NCP", "Hanuman LITE NCP", "Krud LITE NCP", "Greet LITE NCP"],
    ["CB BLACK NCP", "Hanuman Black NCP"],
    ["CAMBODIA COLA", "Coca Cola 330ml"],
    ["WURKZ", "Boostrong", "Krud ED"],
    ["Wurkz Ice", "Champion", "King Kong Ice", "Krud Ice"],
    ["CAMBODIA ED", "Super Boostrong", "King Kong", "AIRA"],
    ["DAZZ", "BACCHUSE", "Dragon"],
    ["DAZZ Zero Sugar", "BACCHUSE Sugar Free"],
    ["IZE PET 300ml Flavour", "POP Z Flavour", "V Cola 350ml"],
    ["IZE COLA PET 1.5L All SKUs", "Coca 1.5L", "Big Cola 3L"],
    ["EXPREZ Melon", "EXPREZ Can 330ml", "Sting Can 330ml", "Idol Can 330ml"],
    ["CAMBODIA Sport 500mL", "CAMBODIA Sport 300ml", "Pocari Sweat", "V-Active Sport"],
    ["CAMBODIA WATER 500mL", "Vital 500mL", "Provida 500mL", "Ganzberg 500ml", "Hitech 500mL"],
    ["CAMBODIA WATER 1500mL", "Vital 1500mL", "Provida 1500mL", "Ganzberg 1500ml", "Hitech 1500mL"],
]

PRODUCT_CODES = {
    "CB LITE ORD": ["cb_lite_ord", "cbc_lite_ord"],
    "CBC 4.4 NCP": ["cbc44_ncp", "cbc_4_4_ncp", "cbc44", "cbc_4_4"],
    "CB Original NCP": ["cb_original_ncp", "cb_original", "cb_original_beer", "cb_original_can", "cb_ori"],
    "CB LITE NCP": ["cb_lite_ncp", "cbc_lite_ncp", "cb_lite", "cbc_lite"],
    "CB BLACK NCP": ["cb_black_ncp", "cb_black"],
    "CAMBODIA COLA": ["cambodia_cola_330", "cambodia_cola", "cambodia_cola_330ml"],
    "WURKZ": ["wurkz"],
    "CAMBODIA ED": ["cambodia_ed", "cambodia_energy", "energy_menthol"],
    "DAZZ": ["dazz"],
    "DAZZ Zero Sugar": ["dazz_zero_sugar", "dazz_zero"],
    "IZE PET 300ml Flavour": ["ize_pet_300_flavour", "ize_pet_300", "ize_pet_300_all", "ize_pet_300ml"],
    "IZE COLA PET 1.5L All SKUs": ["ize_cola_pet_1500", "ize_cola_pet_15_all", "ize_cola_1500"],
    "EXPREZ Melon": ["exprez_melon", "exprez_cucumber", "exprez"],
    "Wurkz Ice": ["wurkz_ice"],
    "CAMBODIA Sport 300mL": ["cambodia_sport_300"],
    "CAMBODIA Sport 500mL": ["cambodia_sport_500"],
    "CAMBODIA WATER 500mL": ["cambodia_water_500"],
    "CAMBODIA WATER 1500mL": ["cambodia_water_1500"],
}

COMPETITOR_CODES = {
    "GB SNOW ORD": ["gb_snow_ord"],
    "HANUMAN LITE ORD": ["hanuman_lite_ord"],
    "Krud LITE ORD": ["krud_lite_ord"],
    "CB Original NCP": ["cb_original_ncp", "cb_original"],
    "GB Original NCP": ["gb_original_ncp", "gb_original"],
    "Krud NCP": ["krud_ncp", "krud"],
    "GB SNOW NCP": ["gb_snow_ncp", "gb_snow"],
    "Hanuman LITE NCP": ["hanuman_lite_ncp", "hanuman_lite"],
    "Krud LITE NCP": ["krud_lite_ncp", "krud_lite"],
    "Greet LITE NCP": ["greet_lite_ncp", "greet_lite", "great_lite"],
    "Hanuman Black NCP": ["hanuman_black_ncp", "hanuman_black"],
    "Coca Cola 330ml": ["coca_cola_330"],
    "Boostrong": ["boostrong"],
    "Krud ED": ["krud_ed"],
    "Champion": ["champion"],
    "King Kong Ice": ["king_kong_ice"],
    "Krud Ice": ["krud_ice"],
    "Super Boostrong": ["super_boostrong"],
    "King Kong": ["king_kong"],
    "AIRA": ["aira"],
    "BACCHUSE": ["bacchuse"],
    "Dragon": ["dragon"],
    "BACCHUSE Sugar Free": ["bacchuse_sugar_free"],
    "POP Z Flavour": ["pop_z_flavour"],
    "V Cola 350ml": ["v_cola_350"],
    "Coca 1.5L": ["coca_1500", "coca_15l", "coca_1_5l"],
    "Big Cola 3L": ["big_cola_3l"],
    "EXPREZ Can 330ml": ["exprez_can_330"],
    "Sting Can 330ml": ["sting_can_330"],
    "Idol Can 330ml": ["idol_can_330"],
    "CAMBODIA Sport 300ml": ["cambodia_sport_300"],
    "Pocari Sweat": ["pocari_sweat"],
    "V-Active Sport": ["v_active_sport"],
    "Vital 500mL": ["vital_500"],
    "Provida 500mL": ["provida_500"],
    "Ganzberg 500ml": ["ganzberg_500"],
    "Hitech 500mL": ["hitech_500"],
    "Vital 1500mL": ["vital_1500"],
    "Provida 1500mL": ["provida_1500"],
    "Ganzberg 1500ml": ["ganzberg_1500"],
    "Hitech 1500mL": ["hitech_1500"],
}

PRODUCT_LABEL_ALIASES = {
    "CB LITE ORD": ["CB LITE ORD", "CBC LITE ORD"],
    "CBC 4.4 NCP": ["CBC 4.4 NCP", "CBC 4.4"],
    "CB Original NCP": ["CB Original NCP", "CB Original"],
    "CB LITE NCP": ["CB LITE NCP", "CB LITE", "CBC LITE"],
    "CB BLACK NCP": ["CB BLACK NCP", "CB BLACK"],
    "CAMBODIA COLA": ["CAMBODIA COLA", "CAMBODIA COLA 330ml"],
    "CAMBODIA ED": ["CAMBODIA ED", "ភេសជ្ជៈប៉ូវកម្លាំង​កម្ពុជា"],
    "IZE PET 300ml Flavour": ["IZE PET 300ml Flavour", "IZE PET 300ml All SKUs"],
    "EXPREZ Melon": ["EXPREZ Melon", "EXPREZ ត្រសក់ផ្អែម"],
    "CAMBODIA Sport 300mL": ["CAMBODIA Sport 300mL", "CAMBODIA Sport 300ml"],
    "CAMBODIA Sport 500mL": ["CAMBODIA Sport 500mL", "CAMBODIA Sport 500ml"],
    "GB Original NCP": ["GB Original NCP", "GB Original", "GB  Original"],
    "GB SNOW NCP": ["GB SNOW NCP", "GB SNOW"],
    "Hanuman LITE NCP": ["Hanuman LITE NCP", "Hanuman Lite"],
    "Krud NCP": ["Krud NCP", "Krud"],
    "Krud LITE NCP": ["Krud LITE NCP", "Krud Lite"],
    "Greet LITE NCP": ["Greet LITE NCP", "Greet Lite", "Great Lite"],
    "Hanuman Black NCP": ["Hanuman Black NCP", "Hanuman Black"],
    "Ganzberg 500ml": ["Ganzberg 500ml", "Ganzberg  500ml"],
}

STATUS_TO_MOVEMENT = {
    "no_sale": 0,
    "sale": 5,
    "fast_sale": 10,
    "អត់មានលក់": 0,
    "មានលក់": 5,
    "លក់ដាច់": 10,
}

STATUS_AVAILABLE = {"sale", "fast_sale", "មានលក់", "លក់ដាច់"}
STOCK_LABEL = {"full": "គ្រប់", "low": "ខ្វះ", "no_stock": "ដាច់ស្តុក"}


def slug(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in str(text)).strip("_").replace("__", "_")


def _normalize_key(key: str) -> str:
    return str(key).strip().lower().split("/")[-1]


def _loose_key(key: str) -> str:
    """Loose key for matching Kobo field labels.

    Removes punctuation, spaces and separators, so
    "GB Original - Movement Score 0-10" can match small export variations.
    """
    s = str(key or "").strip().lower().split("/")[-1]
    return "".join(ch for ch in s if ch.isalnum())


def _key_norm(value: Any) -> str:
    """Normalize Kobo/wide-table field names for tolerant matching.

    Examples that become close enough to match:
    - "GB Original - Movement Score 0-10"
    - "gb_original_movement_score_0_10"
    - "competitor_group/comp_mov_gb_original"
    """
    text_value = str(value or "").strip().lower().split("/")[-1]
    # Treat multiple spaces, underscores, dashes, brackets and Khmer zero-width
    # characters consistently.
    text_value = text_value.replace("\u200b", "")
    return "".join(ch for ch in text_value if ch.isalnum())


def first_value(payload: dict, keys: list[str]):
    """Return the first non-empty payload value for many possible field names.

    Kobo can return fields as XLSForm names, full group paths, human labels, or
    SQL-safe wide-table columns. This reader tries exact, lowercase, and strongly
    normalized matching so renamed labels such as GB Original still resolve.
    """
    if not payload:
        return None

    # 1) Exact match.
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]

    # 2) Case-insensitive exact match.
    lower_map = {str(k).strip().lower(): k for k in payload.keys()}
    for key in keys:
        real_key = lower_map.get(str(key).strip().lower())
        if real_key is not None and payload.get(real_key) not in (None, ""):
            return payload.get(real_key)

    # 3) Normalized match. This fixes fields like
    #    gb_original_movement_score_0_10 vs GB Original - Movement Score 0-10.
    norm_map = {_key_norm(k): k for k in payload.keys()}
    for key in keys:
        real_key = norm_map.get(_key_norm(key))
        if real_key is not None and payload.get(real_key) not in (None, ""):
            return payload.get(real_key)

    # 4) Backward-compatible group-path leaf-name match.
    leaf_map = {_normalize_key(k): k for k in payload.keys()}
    for key in keys:
        real_key = leaf_map.get(_normalize_key(key))
        if real_key is not None and payload.get(real_key) not in (None, ""):
            return payload.get(real_key)

    return None


def to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(str(value).replace(",", "").strip())))
    except Exception:
        return None


def report_number(value):
    """Return clean report number: 52000.0 -> 52000, 6.25 -> 6.25."""
    if value in (None, "", "nan"):
        return None
    try:
        f = float(str(value).replace(",", "").strip())
        return int(f) if f.is_integer() else round(f, 2)
    except Exception:
        return value


def mode(values: list[Any]):
    clean = [v for v in values if v not in (None, "", "nan")]
    if not clean:
        return None
    return Counter(map(str, clean)).most_common(1)[0][0]


def mode_number(values: list[Any]):
    return report_number(mode(values))


def round_half_up(value: float) -> int:
    """Business rounding: decimal .0-.4 down, .5-.9 up.

    Python's built-in round() uses bankers rounding, so 2.5 can become 2.
    This function always makes 2.5 -> 3, 7.75 -> 8.
    """
    return int(value + 0.5)


def average_int(values: list[Any]) -> int | None:
    nums = [to_float(v) for v in values]
    nums = [v for v in nums if v is not None]
    if not nums:
        return None
    return round_half_up(sum(nums) / len(nums))


def movement_average(values: list[Any]) -> float | None:
    """Return raw average movement score from outlet submissions."""
    nums = [to_float(v) for v in values]
    nums = [v for v in nums if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def final_offtake_movement(values: list[Any]) -> int | None:
    """Base movement from average, before compare-group promotion.

    Rule:
    1) Average valid submitted movement values.
    2) Round using KB business rounding: .0-.4 down, .5-.9 up.
    3) Keep that rounded score here.

    The comparison-row goal rule is applied later by
    _apply_offtake_comparison_goal(): the product with the largest raw
    average becomes 10, the same increase is applied to its comparison
    products, and duplicate positive ratings are removed by average rank.

    Examples before comparison promotion:
      7.75 -> 8
      8.20 -> 8
      8.90 -> 9
    """
    avg = movement_average(values)
    if avg is None:
        return None

    rounded_score = round_half_up(avg)
    return max(0, min(10, rounded_score))

def _get_movement_bucket(result: dict, product: str) -> tuple[str, dict[str, Any]] | None:
    """Return (bucket_name, product_data) for own or competitor product."""
    products = result.get("products") or {}
    competitors = result.get("competitors") or {}

    # These two are own-product freshness rows but appear in competitor
    # columns in the movement table, so comparison promotion must update the
    # competitor bucket that Excel actually reads.
    if product in {"CB Original NCP", "CAMBODIA Sport 300ml"} and product in competitors:
        return "competitors", competitors[product]
    if product in products:
        return "products", products[product]
    if product in competitors:
        return "competitors", competitors[product]

    alias_map = {
        "CBC LITE ORD": "CB LITE ORD",
        "CAMBODIA COLA 330ml": "CAMBODIA COLA",
        "IZE PET 300ml All SKUs": "IZE PET 300ml Flavour",
        "CAMBODIA Sport 300mL": "CAMBODIA Sport 300ml",
        "CAMBODIA Sport 300ml": "CAMBODIA Sport 300mL",
        "Ganzberg  500ml": "Ganzberg 500ml",
    }
    alias = alias_map.get(product)
    if alias in products:
        return "products", products[alias]
    if alias in competitors:
        return "competitors", competitors[alias]
    return None


def _apply_offtake_comparison_goal(result: dict) -> None:
    """Normalize movement scores inside every comparison row.

    Business rule:
    1) Calculate each product's raw average and KB rounded movement first.
    2) Find the product with the largest raw average in the comparison row.
    3) Raise that winner to 10.
    4) Add the same increase amount to every other product with real movement.
    5) Remove duplicate visible ratings by ranking products by raw average.
       The row therefore contains only one movement 10 and no duplicate
       positive movement scores.

    Examples:
      Rounded 7, 5, 4, 3, 2 -> increase 3 -> final 10, 8, 7, 6, 5.

      Average 7.75, 8.20, 8.90
      Rounded 8, 8, 9 -> increase 1 -> preliminary 9, 9, 10.
      Raw-average ranking removes the duplicate -> final 8, 9, 10.

    Missing values stay blank. A real zero stays zero and is not promoted,
    because zero means no movement rather than a scored competing product.
    """
    for group in OFFTAKE_COMPARE_GROUPS:
        items: list[dict[str, Any]] = []
        seen_ids: set[int] = set()

        for order, product in enumerate(group):
            found = _get_movement_bucket(result, product)
            if not found:
                continue

            _, pdata = found
            if id(pdata) in seen_ids:
                continue
            seen_ids.add(id(pdata))

            rounded = to_int(pdata.get("mov"))
            avg = to_float(pdata.get("_mov_avg"))

            if rounded is None:
                pdata["mov"] = None
                continue

            rounded = max(0, min(10, rounded))
            pdata["mov"] = rounded

            # Do not invent movement for products submitted as zero/no sale.
            if rounded <= 0:
                continue

            # Current aggregation always stores _mov_avg. The fallback keeps
            # legacy rows usable if only their rounded movement is available.
            if avg is None:
                avg = float(rounded)

            items.append({
                "data": pdata,
                "product": product,
                "rounded": rounded,
                "avg": avg,
                "order": order,
            })

        if not items:
            continue

        # Winner is selected by raw average, not only by rounded movement.
        winner = max(
            items,
            key=lambda item: (item["avg"], item["rounded"], -item["order"]),
        )
        increase = max(0, 10 - winner["rounded"])

        for item in items:
            item["shifted"] = min(10, item["rounded"] + increase)

        # Highest raw average receives the highest final movement. When two
        # preliminary values duplicate, lower-ranked products step down by one
        # until every positive score in the row is unique.
        ranked = sorted(
            items,
            key=lambda item: (-item["avg"], -item["rounded"], item["order"]),
        )

        previous_score = 11
        for item in ranked:
            final_score = min(item["shifted"], previous_score - 1)
            final_score = max(1, min(10, final_score))
            item["data"]["mov"] = final_score
            previous_score = final_score

def _clean_location_piece(text: Any) -> str:
    """Clean one user-entered location phrase without destroying meaning."""
    value = str(text or "").replace("\r", " ").replace("\n", " ")
    value = re.sub(r"\s+", " ", value).strip(" ,;|/\\")
    return value


def _romanize_known_khmer_location(text: str) -> str:
    """Map a few common Khmer place names to a comparable English key.

    This does not remove the original Khmer display text. It is only used for
    duplicate detection, so ព្រែកព្នៅ can match Prek Pnov/Praek Pnov/Pnov.
    """
    khmer_aliases = {
        "ព្រែកព្នៅ": "prek pnov",
        "ភ្នំពេញ": "phnom penh",
        "ដំបូកខ្ពស់": "dambok khpos",
        "អូដឹម": "odem",
        "ផ្សារ": "psar",
    }
    for kh, en in khmer_aliases.items():
        text = text.replace(kh, f" {en} ")
    return text


def _location_key(text: str) -> str:
    """Create a smart duplicate-detection key for any user-filled location.

    The key is intentionally tolerant:
    - ignores upper/lower case and extra spaces
    - removes generic words like Market/Psar/Village/Commune
    - normalizes common spelling variants: praek/preak/prey -> prek
    - handles close spellings by being used with SequenceMatcher later
    - maps common Khmer place text to the same comparable key
    """
    text = _clean_location_piece(text).lower().replace("\u200b", "")
    text = _romanize_known_khmer_location(text)

    # Normalize separators and common punctuation.
    text = re.sub(r"[,;|/\\()\[\]{}:._\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # General word cleanup. These words often make the same place look
    # different but do not identify the unique location.
    remove_words = {
        "market", "psar", "phsar", "ផ្សារ",
        "village", "commune", "district", "province", "city", "area",
        "khan", "sangkat", "phum", "khum", "sruk", "krong",
        "near", "around", "at", "in", "the",
    }
    words = [w for w in text.split() if w not in remove_words]
    text = " ".join(words)

    # Common spelling normalization. This helps with real user typing where the
    # same place is entered as Prek/Praek/Preak/Prey, Somroung/Samroang, etc.
    replacements = {
        "phnom penh": "phnompenh",
        "pnom penh": "phnompenh",
        "pn penh": "phnompenh",
        "praek": "prek",
        "preaek": "prek",
        "preak": "prek",
        "prey": "prek",
        "pnov": "pnov",
        "pnow": "pnov",
        "pov": "pnov",
        "somroung": "samroang",
        "somrong": "samroang",
        "samrong": "samroang",
        "saroang": "samroang",
        "saraong": "samroang",
        "saroeng": "samroang",
    }
    for src, dst in replacements.items():
        text = re.sub(rf"\b{re.escape(src)}\b", dst, text)

    # Specific compound normalization after word normalization.
    text = text.replace("prek pnov", "prekpnov")
    text = text.replace("prekpnov", "prekpnov")
    text = text.replace("pnov", "prekpnov") if text == "pnov" else text

    return "".join(ch for ch in text if ch.isalnum())


def _is_similar_location(new_key: str, old_key: str) -> bool:
    """Return True when two normalized location keys mean the same place."""
    if not new_key or not old_key:
        return False

    if new_key == old_key:
        return True

    # A short/long version of the same place, e.g. prekpnov vs phnompenhprekpnov.
    if len(new_key) >= 5 and len(old_key) >= 5 and (new_key in old_key or old_key in new_key):
        return True

    # Fuzzy spelling similarity for user-filled text. Use a higher threshold for
    # short keys to avoid merging different short locations by mistake.
    ratio = difflib.SequenceMatcher(None, new_key, old_key).ratio()
    threshold = 0.90 if min(len(new_key), len(old_key)) < 7 else 0.84
    return ratio >= threshold


def _preferred_location_label(part: str, key: str) -> str:
    """Return a clean display label for known duplicate location variants."""
    if key == "prekpnov" or key.endswith("prekpnov"):
        return "Prek Pnov"
    if key == "samroang":
        return "Samroang"
    if key == "phnompenh":
        return "Phnom Penh"
    return _clean_location_piece(part)


def combine_location_visit(values: list[Any]) -> str:
    """Combine Location Visit text from all outlet submissions.

    This is designed for unpredictable user input. It does not depend only on a
    fixed list of locations; it uses normalization + fuzzy matching to remove
    duplicates while keeping genuinely different places.
    """
    seen_keys: list[str] = []
    parts: list[str] = []

    for value in values:
        text = _clean_text(value)
        if not text:
            continue

        # Split only on strong separators. Do not split on spaces because a
        # location name often contains multiple words.
        for piece in re.split(r"[,;|/\n\r]+", text.replace("，", ",").replace("、", ",")):
            part = _clean_location_piece(piece)
            if not part:
                continue

            key = _location_key(part)
            if not key:
                continue

            if any(_is_similar_location(key, old_key) for old_key in seen_keys):
                continue

            seen_keys.append(key)
            label = _preferred_location_label(part, key)
            if label and label not in parts:
                parts.append(label)

    return ", ".join(parts)

def yes_value(value: Any) -> bool:
    if value in (None, ""):
        return False
    s = str(value).strip().lower()
    return s in {"1", "yes", "y", "true", "មាន", "មានលក់", "លក់ដាច់", "new", "ថ្មី", "sale", "fast_sale"}


def _status_to_mov(value: Any) -> int | None:
    if value in (None, ""):
        return None
    s = str(value).strip()
    return STATUS_TO_MOVEMENT.get(s) if s in STATUS_TO_MOVEMENT else STATUS_TO_MOVEMENT.get(s.lower())


def _stock_label(value: Any) -> str | None:
    if value in (None, ""):
        return None
    s = str(value).strip()
    return STOCK_LABEL.get(s) or s


def stock_summary(values: list[Any]) -> str | None:
    labels = [_stock_label(v) for v in values]
    labels = [v for v in labels if v not in (None, "", "nan")]
    if not labels:
        return None
    total = len(labels)
    counts = Counter(labels)
    if counts.get("ដាច់ស្តុក", 0) / total >= 0.50:
        return "ដាច់ស្តុក"
    if counts.get("ខ្វះ", 0) / total >= 0.60:
        return "ខ្វះ"
    if counts.get("គ្រប់", 0) / total >= 0.70:
        return "គ្រប់"
    return counts.most_common(1)[0][0]



def _field_label_aliases(product: str, field: str) -> list[str]:
    """Return label aliases for current and legacy Kobo product names."""
    labels: list[str] = []
    names = PRODUCT_LABEL_ALIASES.get(product, [product])
    for display_name in names:
        if field in {"mov", "movement", "movement_score"}:
            labels += [
                f"{display_name} - Movement Score 0-10",
                f"{display_name} - Movement Score",
                f"{display_name} - Offtake Movement",
                f"{display_name} - Movement",
            ]
        elif field == "status":
            labels += [
                f"{display_name} - ស្ថានភាពលក់",
                f"{display_name} - Sale Status",
                f"{display_name} - Status",
            ]
        elif field == "stock":
            labels += [f"{display_name} - Stock Status", f"{display_name} - ស្ថានភាពស្តុក"]
        elif field == "bbe":
            labels += [
                f"{display_name} - BBE / Freshness Date",
                f"{display_name} - BBE",
                f"{display_name} - Freshness Date",
            ]
        elif field == "buy_in":
            labels += [f"{display_name} - Buy In Price", f"{display_name} - Buy In"]
        elif field == "sell_out":
            labels += [f"{display_name} - Sell Out Price", f"{display_name} - Sell Out"]
        elif field == "ring_pull":
            labels += [
                f"{display_name} - Ring Pull (រៀល\u200b)",
                f"{display_name} - Ring Pull (រៀល)",
                f"{display_name} - Ring Pull",
            ]
        elif field == "volume":
            labels += [
                f"{display_name} - Volume",
                f"{display_name} - Volume (ctn)",
                f"{display_name} - Volume Ctn",
            ]
        elif field == "new_purchase":
            labels += [
                f"{display_name} - New Outlet Purchase",
                f"{display_name} - New Purchase",
            ]

    more: list[str] = []
    for label in labels:
        more.append(label.replace("  ", " "))
        more.append(label.replace("GB Original", "GB  Original"))
        more.append(label.replace("GB  Original", "GB Original"))
    return list(dict.fromkeys(labels + more))


def product_field(product: str, field: str) -> list[str]:
    codes = PRODUCT_CODES.get(product, [slug(product)])
    keys: list[str] = []
    keys += _field_label_aliases(product, field)
    for code in codes:
        field_aliases = [field]
        if field == "mov":
            field_aliases += ["movement", "movement_score"]
        elif field == "stock":
            field_aliases += ["stock_status"]
        elif field == "buy_in":
            field_aliases += ["buy_in_price"]
        elif field == "sell_out":
            field_aliases += ["sell_out_price"]
        elif field == "ring_pull":
            field_aliases += ["ring_pull_price", "ring_pull_riel"]
        elif field == "status":
            field_aliases += ["fresh_status"]
        for fa in dict.fromkeys(field_aliases):
            keys += [
                f"fresh_{fa}_{code}",
                f"{code}_{fa}",
                f"{fa}_{code}",
                f"products/{code}_{fa}",
                f"own/{code}_{fa}",
                f"own_product_group/{code}_{fa}",
                f"freshness_availability_group/{code}_{fa}",
                f"freshness_availability_group/fresh_{fa}_{code}",
                f"fresh_{code}_group/fresh_{fa}_{code}",
                f"freshness_availability_group/fresh_{code}_group/fresh_{fa}_{code}",
            ]
    return keys


def competitor_field(product: str, field: str) -> list[str]:
    codes = COMPETITOR_CODES.get(product, [slug(product)])
    keys: list[str] = []
    keys += _field_label_aliases(product, field)
    # Some report comparison items are also own-product freshness rows
    # (CB Original NCP and CAMBODIA Sport 300ml). Reuse their own form fields.
    own_alias = "CAMBODIA Sport 300mL" if product == "CAMBODIA Sport 300ml" else product
    if own_alias in OWN_PRODUCTS:
        keys += product_field(own_alias, field)
    for code in codes:
        field_aliases = [field]
        if field == "mov":
            field_aliases += ["movement", "movement_score"]
        elif field == "status":
            field_aliases += ["comp_status"]
        elif field == "stock":
            field_aliases += ["stock_status"]
        elif field == "buy_in":
            field_aliases += ["buy_in_price"]
        elif field == "sell_out":
            field_aliases += ["sell_out_price"]
        elif field == "volume":
            field_aliases += ["volume_ctn"]
        for fa in dict.fromkeys(field_aliases):
            keys += [
                f"comp_{fa}_{code}",
                f"comp_{code}_{fa}",
                f"{code}_{fa}",
                f"competitor/{code}_{fa}",
                f"competitors/{code}_{fa}",
                f"competitor_products/{code}_{fa}",
                f"competitor_group/{code}_{fa}",
                f"competitor_group/comp_{fa}_{code}",
                f"comp_{code}_group/comp_{fa}_{code}",
                f"competitor_group/comp_{code}_group/comp_{fa}_{code}",
            ]
    return keys


def is_available(payload: dict, product: str) -> bool:
    status = first_value(payload, product_field(product, "status"))
    if status not in (None, ""):
        return str(status).strip().lower() in STATUS_AVAILABLE or str(status).strip() in STATUS_AVAILABLE
    for f in ("mov", "bbe", "stock", "buy_in", "sell_out", "ring_pull"):
        if own_product_field_enabled(product, f) and first_value(
            payload, product_field(product, f)
        ) not in (None, ""):
            return True
    return yes_value(first_value(payload, product_field(product, "available")))


def _clean_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).replace("\r", "\n").strip()


FINAL_SUMMARY_KEYWORDS = (
    "បូកសរុបរួម",
    "បូកសរុបរូម",
    "សរុបរួម",
    "បួកសរុបរួម",
)


def is_final_summary_outlet_name(value: Any) -> bool:
    """Return True only when Outlet Name is one of the four summary markers.

    The marker is matched exactly after trimming whitespace. It is no longer
    searched inside Key Issues or Initiative/Suggestion text.
    """
    normalized = _clean_text(value).replace(" ", "")
    return normalized in {keyword.replace(" ", "") for keyword in FINAL_SUMMARY_KEYWORDS}


def _is_summary_submission(submission: Any) -> bool:
    return is_final_summary_outlet_name(getattr(submission, "outlet_name", None))


def _strip_final_summary_keyword(value: Any) -> str:
    text_value = _clean_text(value)
    for keyword in FINAL_SUMMARY_KEYWORDS:
        text_value = text_value.replace(keyword, "")
    return text_value.strip(" :-–—|\n\t")


def _summary_points(value: Any, limit: int = 4) -> list[str]:
    text_value = _strip_final_summary_keyword(value)
    if not text_value:
        return []
    pieces = re.split(r"(?:\r?\n)+|[;；]+|(?:(?<=^)|(?<=\s))[1-4][.)៖:]\s*|[•▪◦●]+", text_value)
    cleaned: list[str] = []
    for piece in pieces:
        item = re.sub(r"^[-–—*]+\s*", "", str(piece or "")).strip()
        if item and item not in cleaned:
            cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _latest_manual_summary(submissions: list) -> tuple[list[str], list[str]]:
    # Summary selection is controlled only by Outlet Name. The Key Issues and
    # Suggestion fields contain the actual summary text and need no keyword.
    candidates = [s for s in submissions if _is_summary_submission(s)]
    if not candidates:
        return [], []
    latest = max(
        candidates,
        key=lambda s: (
            getattr(s, "submission_time", None) or datetime.min,
            getattr(s, "id", 0) or 0,
        ),
    )
    return (
        _summary_points(getattr(latest, "key_issue_text", None)),
        _summary_points(getattr(latest, "suggestion_text", None)),
    )


def _product_lookup_key(name: Any) -> str:
    """Very loose product key for alias matching: GB  Original == GB Original."""
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


def _canonical_product_name(name: Any) -> str:
    """Canonical product name used for current template and legacy DB rows."""
    value = " ".join(str(name or "").replace("\u200b", "").split()).strip()
    aliases = {
        "CBC LITE ORD": "CB LITE ORD",
        "CB LITE ORD": "CB LITE ORD",
        "CBC 4.4": "CBC 4.4 NCP",
        "CB Original": "CB Original NCP",
        "CB LITE": "CB LITE NCP",
        "CBC LITE": "CB LITE NCP",
        "CB BLACK": "CB BLACK NCP",
        "CAMBODIA COLA 330ml": "CAMBODIA COLA",
        "ភេសជ្ជៈប៉ូវកម្លាំង_កម្ពុជា": "CAMBODIA ED",
        "ភេសជ្ជៈប៉ូវកម្លាំង​កម្ពុជា": "CAMBODIA ED",
        "IZE PET 300ml All SKUs": "IZE PET 300ml Flavour",
        "EXPREZ ត្រសក់ផ្អែម": "EXPREZ Melon",
        "GB Original": "GB Original NCP",
        "GB  Original": "GB Original NCP",
        "GB SNOW": "GB SNOW NCP",
        "Hanuman Lite": "Hanuman LITE NCP",
        "Krud": "Krud NCP",
        "Krud Lite": "Krud LITE NCP",
        "Great Lite": "Greet LITE NCP",
        "Greet Lite": "Greet LITE NCP",
        "Hanuman Black": "Hanuman Black NCP",
        "Ganzberg  500ml": "Ganzberg 500ml",
        "CAMBODIA Sport 300mL": "CAMBODIA Sport 300mL",
        "CAMBODIA Sport 300ml": "CAMBODIA Sport 300ml",
    }
    return aliases.get(value, value)


def _metric_by_product(metrics: list) -> dict[str, Any]:
    """Map metrics by both original and canonical product name.

    This prevents template/code naming differences from causing wrong report
    values, especially GB Original.
    """
    result: dict[str, Any] = {}
    for m in (metrics or []):
        raw = getattr(m, "product_name", None)
        if raw in (None, ""):
            continue
        raw_name = str(raw).strip()
        canonical = _canonical_product_name(raw_name)
        result[raw_name] = m
        result[canonical] = m
        result[_product_lookup_key(raw_name)] = m
        result[_product_lookup_key(canonical)] = m
    return result


def _value(obj, attr: str):
    return getattr(obj, attr, None) if obj is not None else None



def _payload_of_submission(submission: Any) -> dict:
    """Return the raw Kobo payload/json data from a submission object.

    Older rows may have missing metric rows when a product label changed
    (example: GB  Original -> GB Original). Reading the raw payload as fallback
    keeps reports correct without needing to delete/resync old data.
    """
    for attr in ("payload", "raw_payload", "data", "json_data", "submission_payload"):
        value = getattr(submission, attr, None)
        if isinstance(value, dict):
            return value
    return {}



def _loose_product_tokens(product: str) -> list[str]:
    """Tokens used for loose movement-field detection."""
    normalized = _canonical_product_name(product)
    tokens = re.findall(r"[a-z0-9]+", normalized.lower())
    return [t for t in tokens if t not in {"ml", "m", "l", "all", "skus"}]


def _is_movement_key_for_product(key: Any, product: str, is_competitor: bool) -> bool:
    """Detect movement columns when exact aliases fail.

    This is designed for kobo_submissions_wide columns. It fixes cases like
    GB Original where the wide table might contain names such as:
    - gb_original_movement_score_0_10
    - comp_movement_score_gb_original
    - competitor_products_gb_original_movement_score_0_10
    """
    norm_key = _key_norm(key)
    if not norm_key:
        return False

    # Must look like a movement/offtake score field.
    movement_words = ("mov", "movement", "offtake", "score")
    if not any(word in norm_key for word in movement_words):
        return False

    # Avoid stock/status/buy/sell/ring/volume fields.
    blocked_words = (
        "status", "stock", "bbe", "freshness", "buyin", "sellout",
        "ringpull", "qty", "quantity", "volume", "available", "availability",
    )
    if any(word in norm_key for word in blocked_words):
        return False

    tokens = _loose_product_tokens(product)
    if not tokens:
        return False

    # Every product token must be present. This prevents GB Original from
    # matching GB SNOW or other GB products.
    return all(token in norm_key for token in tokens)


def _loose_movement_value(payload: dict, product: str, is_competitor: bool) -> int | None:
    """Fallback scanner for movement values in raw/wide Kobo rows."""
    if not payload:
        return None

    candidates: list[tuple[str, Any]] = []
    for key, value in payload.items():
        if value in (None, ""):
            continue
        if _is_movement_key_for_product(key, product, is_competitor):
            mov = to_int(value)
            if mov is not None:
                candidates.append((str(key), mov))

    if not candidates:
        return None

    # Prefer competitor-prefixed columns for competitor values and fresh/own
    # columns for own product values if available. Otherwise use first found.
    if is_competitor:
        for key, mov in candidates:
            nk = _key_norm(key)
            if nk.startswith("comp") or "competitor" in nk:
                return mov
    else:
        for key, mov in candidates:
            nk = _key_norm(key)
            if nk.startswith("fresh") or "own" in nk or "product" in nk:
                return mov

    return candidates[0][1]


def _movement_from_payload(payload: dict, product: str, is_competitor: bool) -> int | None:
    """Read product movement directly from Kobo payload/wide row.

    Order:
    1. Known aliases from XLSForm/template labels.
    2. Loose scan of all wide-table/raw payload columns.
    3. Status-to-movement fallback.
    """
    keys = competitor_field(product, "mov") if is_competitor else product_field(product, "mov")
    value = first_value(payload, keys)
    mov = to_int(value)
    if mov is not None:
        return mov

    # Critical fallback for renamed/sanitized columns such as GB Original.
    mov = _loose_movement_value(payload, product, is_competitor)
    if mov is not None:
        return mov

    status_keys = competitor_field(product, "status") if is_competitor else product_field(product, "status")
    status_value = first_value(payload, status_keys)

# For competitors, blank status should NOT become 0.
# Only use status fallback when the user actually answered status.
    if status_value not in (None, ""):
       return _status_to_mov(status_value)

    return None

def _metric_or_payload_movement(submission: Any, metric: Any, product: str, is_competitor: bool) -> int | None:
    """Use metric table movement first, then fallback to raw Kobo payload."""
    mov = _value(metric, "movement_score")
    if mov is not None:
        return to_int(mov)
    return _movement_from_payload(_payload_of_submission(submission), product, is_competitor)


def _include_movement_value(value: Any, is_competitor: bool) -> bool:
    """Decide whether a movement value should be included in averaging.

    Important for competitor products:
    In the KoBo wide export, blank competitor fields can appear as 0. Those 0s
    mean "not answered / not selected", not a real movement score. If we include
    those zeros, GB Original values like [7, 2, 10, 10, 10, 10] become polluted
    as [10, 0, 10, 0, ...] and the final movement incorrectly becomes 2.

    Rule:
    - Own products: keep 0 because own-product no-sale/0 can be meaningful.
    - Competitors: ignore 0 and blanks; count only filled competitor ratings 1-10.
    """
    if value in (None, "", "nan"):
        return False

    mov = to_int(value)
    if mov is None:
        return False

    if is_competitor and mov == 0:
        return False

    return True




def _metric_or_payload_value(submission: Any, metric: Any, product: str, field: str, is_competitor: bool):
    """Generic fallback reader for report fields.

    This is especially useful after form/template product-name updates because
    old DB metric rows may not contain every product, while the raw payload still
    has the submitted values. Disabled own-product fields return blank even when
    historical rows still contain old values.
    """
    field_map = {
        "bbe_date": "bbe",
        "stock_status": "stock",
        "buy_in_price": "buy_in",
        "sell_out_price": "sell_out",
        "ring_pull_value": "ring_pull",
        "volume_ctn": "volume",
    }
    logical_field = field_map.get(field, field)
    if not is_competitor and not own_product_field_enabled(product, logical_field):
        return None

    value = _value(metric, field)
    if value not in (None, ""):
        return value

    payload = _payload_of_submission(submission)
    if not payload:
        return None

    keys = competitor_field(product, logical_field) if is_competitor else product_field(product, logical_field)
    return first_value(payload, keys)


def _metric_or_payload_available(submission: Any, metric: Any, product: str) -> bool:
    # Prefer current form status/movement over a legacy stored available flag.
    metric_status = _value(metric, "status")
    if metric_status not in (None, ""):
        return (
            str(metric_status).strip().lower() in STATUS_AVAILABLE
            or str(metric_status).strip() in STATUS_AVAILABLE
        )

    movement = to_int(_value(metric, "movement_score"))
    if movement is not None:
        return movement > 0

    payload = _payload_of_submission(submission)
    if not payload:
        return False

    status = first_value(payload, product_field(product, "status"))
    if status not in (None, ""):
        return str(status).strip().lower() in STATUS_AVAILABLE or str(status).strip() in STATUS_AVAILABLE

    for field in ("mov", "bbe", "stock", "buy_in", "sell_out", "ring_pull"):
        if own_product_field_enabled(product, field) and first_value(
            payload, product_field(product, field)
        ) not in (None, ""):
            return True
    return False



def _wide_payloads_by_submission(submissions: list[Any]) -> dict[str, dict[str, Any]]:
    """Read normalized/wide Kobo rows for report fallback.

    The production schema removed the raw JSONB payload from kobo_submissions,
    but kobo_submissions_wide still stores each Kobo question as a real SQL
    column. Reading it here fixes cases where a metric row was created with an
    old product label or stale value, for example GB Original showing only one
    outlet value instead of all submitted outlet values.
    """
    ids = [str(getattr(s, "submission_id", "") or "").strip() for s in submissions]
    ids = [sid for sid in ids if sid]
    if not ids:
        return {}

    out: dict[str, dict[str, Any]] = {}
    try:
        with SessionLocal() as db:
            for sid in ids:
                row = db.execute(
                    text("SELECT * FROM public.kobo_submissions_wide WHERE submission_id = :sid"),
                    {"sid": sid},
                ).mappings().first()
                if row:
                    out[sid] = dict(row)
    except Exception as exc:
        # Report generation must continue even if the wide fallback is not
        # available, for example during unit tests or before the wide table is
        # created.
        print(f"⚠️ Wide Kobo fallback unavailable: {exc}")
    return out


def _wide_payload_for_submission(submission: Any, wide_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sid = str(getattr(submission, "submission_id", "") or "").strip()
    return wide_map.get(sid, {})


def _movement_from_wide_or_metric(
    submission: Any,
    metric: Any,
    product: str,
    is_competitor: bool,
    wide_map: dict[str, dict[str, Any]],
) -> int | None:
    """Use kobo_submissions_wide first, then metric table fallback.

    Wide table values are closest to the raw Kobo submitted fields and are not
    affected by old metric product-name aliases. This is especially important
    after renaming `GB  Original` to `GB Original`.
    """
    wide_payload = _wide_payload_for_submission(submission, wide_map)
    if wide_payload:
        mov = _movement_from_payload(wide_payload, product, is_competitor)
        if mov is not None:
            return mov

    return _metric_or_payload_movement(submission, metric, product, is_competitor)


def _value_from_wide_or_metric(
    submission: Any,
    metric: Any,
    product: str,
    field: str,
    is_competitor: bool,
    wide_map: dict[str, dict[str, Any]],
):
    """Read report field from wide table first, then metric table fallback."""
    logical_field = {
        "bbe_date": "bbe",
        "stock_status": "stock",
        "buy_in_price": "buy_in",
        "sell_out_price": "sell_out",
        "ring_pull_value": "ring_pull",
        "volume_ctn": "volume",
    }.get(field, field)
    if not is_competitor and not own_product_field_enabled(product, logical_field):
        return None

    wide_payload = _wide_payload_for_submission(submission, wide_map)
    if wide_payload:
        keys = competitor_field(product, logical_field) if is_competitor else product_field(product, logical_field)
        value = first_value(wide_payload, keys)
        if value not in (None, ""):
            return value

    return _metric_or_payload_value(submission, metric, product, field, is_competitor)


def _available_from_wide_or_metric(
    submission: Any,
    metric: Any,
    product: str,
    wide_map: dict[str, dict[str, Any]],
) -> bool:
    wide_payload = _wide_payload_for_submission(submission, wide_map)
    if wide_payload:
        status = first_value(wide_payload, product_field(product, "status"))
        if status not in (None, ""):
            return str(status).strip().lower() in STATUS_AVAILABLE or str(status).strip() in STATUS_AVAILABLE
        for field in ("mov", "bbe", "stock", "buy_in", "sell_out", "ring_pull"):
            if own_product_field_enabled(product, field) and first_value(
                wide_payload, product_field(product, field)
            ) not in (None, ""):
                return True

    return _metric_or_payload_available(submission, metric, product)

def aggregate_submissions(submissions: list) -> dict:
    all_submissions = list(submissions or [])

    # A row whose Outlet Name is a summary marker is a control/summary row,
    # not a real outlet visit. Exclude it from outlet counts, availability,
    # movement, freshness, Ring Pull and every product calculation.
    data_submissions = [s for s in all_submissions if not _is_summary_submission(s)]
    header_submissions = data_submissions or all_submissions
    first_submission = header_submissions[0] if header_submissions else None

    outlet_types = Counter((s.outlet_type or "Unknown") for s in data_submissions)
    result = {
        "dealer": getattr(first_submission, "dealer", "") if first_submission else "",
        "region": getattr(first_submission, "region", "") if first_submission else "",
        "report_date": getattr(first_submission, "report_date", None) if first_submission else None,
        "total_outlets": len(data_submissions),
        "outlet_types": outlet_types,
        "group_no": to_int(mode([s.group_no for s in header_submissions])) or 2,
        "member_no": to_int(mode([s.member_no for s in header_submissions])),
        "location_text": combine_location_visit([s.location_text for s in data_submissions]),
        "products": {},
        "competitors": {},
        "ring_pull": {},
        "key_issues": [],
        "suggestions": [],
    }

    # Keep the rest of the existing aggregation logic unchanged, but make it
    # operate only on genuine outlet rows.
    submissions = data_submissions

    product_maps = [_metric_by_product(list(getattr(s, "product_metrics", []) or [])) for s in submissions]
    competitor_maps = [_metric_by_product(list(getattr(s, "competitor_metrics", []) or [])) for s in submissions]
    ring_maps = [_metric_by_product(list(getattr(s, "ring_pull_metrics", []) or [])) for s in submissions]
    wide_map = _wide_payloads_by_submission(submissions)

    for product in OWN_PRODUCTS:
        metrics = [pm.get(product) or pm.get(_product_lookup_key(product)) for pm in product_maps]

        movement_values = [
            v for s, m in zip(submissions, metrics)
            if (v := _movement_from_wide_or_metric(s, m, product, is_competitor=False, wide_map=wide_map)) is not None
        ]

        pdata: dict[str, Any] = {
            "bbe": mode([
                _value_from_wide_or_metric(s, m, product, "bbe_date", is_competitor=False, wide_map=wide_map)
                for s, m in zip(submissions, metrics)
            ]) if own_product_field_enabled(product, "bbe") else None,
            "mov": final_offtake_movement(movement_values),
            "_mov_avg": movement_average(movement_values),
            "stock": stock_summary([
                _value_from_wide_or_metric(s, m, product, "stock_status", is_competitor=False, wide_map=wide_map)
                for s, m in zip(submissions, metrics)
            ]) if own_product_field_enabled(product, "stock") else None,
            "buy_in": mode_number([
                _value_from_wide_or_metric(s, m, product, "buy_in_price", is_competitor=False, wide_map=wide_map)
                for s, m in zip(submissions, metrics)
            ]) if own_product_field_enabled(product, "buy_in") else None,
            "sell_out": mode_number([
                _value_from_wide_or_metric(s, m, product, "sell_out_price", is_competitor=False, wide_map=wide_map)
                for s, m in zip(submissions, metrics)
            ]) if own_product_field_enabled(product, "sell_out") else None,
            "ring_pull": mode_number([
                _value_from_wide_or_metric(s, m, product, "ring_pull_value", is_competitor=False, wide_map=wide_map)
                for s, m in zip(submissions, metrics)
            ]) if own_product_field_enabled(product, "ring_pull") else None,
            # Product-level New Outlet Purchase and Volume are removed from the
            # current Kobo workflow for every own product.
            "new_purchase": 0,
            "volume": None,
        }

        counts = Counter()
        for s, m in zip(submissions, metrics):
            if _available_from_wide_or_metric(s, m, product, wide_map):
                counts[s.outlet_type or "Unknown"] += 1
        pdata["availability"] = counts
        result["products"][product] = pdata

    for product in COMPETITOR_PRODUCTS:
        metrics = [cm.get(product) or cm.get(_product_lookup_key(product)) for cm in competitor_maps]
        movement_values = [
            v
            for s, m in zip(submissions, metrics)
            if _include_movement_value(
                (v := _movement_from_wide_or_metric(s, m, product, is_competitor=True, wide_map=wide_map)),
                is_competitor=True,
            )
        ]
        cdata: dict[str, Any] = {
            "mov": final_offtake_movement(movement_values),
            "_mov_avg": movement_average(movement_values),
            "_movement_values": movement_values,
            "stock": stock_summary([
                _value_from_wide_or_metric(s, m, product, "stock_status", is_competitor=True, wide_map=wide_map)
                for s, m in zip(submissions, metrics)
            ]),
            "buy_in": mode_number([
                _value_from_wide_or_metric(s, m, product, "buy_in_price", is_competitor=True, wide_map=wide_map)
                for s, m in zip(submissions, metrics)
            ]),
            "sell_out": mode_number([
                _value_from_wide_or_metric(s, m, product, "sell_out_price", is_competitor=True, wide_map=wide_map)
                for s, m in zip(submissions, metrics)
            ]),
        }
        result["competitors"][product] = cdata

        # Store safe aliases in the result dict. This protects Excel report
        # generation when a template still contains old spacing/hidden-space
        # labels such as "GB  Original" while the data key is "GB Original".
        result["competitors"][_product_lookup_key(product)] = cdata
        result["competitors"][_canonical_product_name(product)] = cdata
        if product == "GB Original NCP":
            result["competitors"]["GB  Original"] = cdata
            result["competitors"]["GB Original"] = cdata
            result["competitors"]["GB Original NCP"] = cdata
            result["competitors"]["gboriginal"] = cdata
            result["competitors"]["gboriginalncp"] = cdata

    # Final hard-normalize GB Original after all competitor aliases are created.
    # This prevents any stale alias/metric row from making the Excel report show
    # the single raw value 2 when the actual submitted values are [7,2,10,10,10,10].
    gb = result.get("competitors", {}).get("GB Original NCP") or result.get("competitors", {}).get("GB Original") or result.get("competitors", {}).get("gboriginalncp")
    if isinstance(gb, dict):
        gb_values = [
            v for v in list(gb.get("_movement_values") or [])
            if _include_movement_value(v, is_competitor=True)
        ]

        # If alias data somehow lost the values, recompute directly from every
        # submission/wide payload one more time.
        if not gb_values:
            gb_metrics = [cm.get("GB Original NCP") or cm.get("GB Original") or cm.get("gboriginalncp") or cm.get("gboriginal") or cm.get("GB  Original") for cm in competitor_maps]
            gb_values = [
                v
                for s, m in zip(submissions, gb_metrics)
                if _include_movement_value(
                    (v := _movement_from_wide_or_metric(s, m, "GB Original NCP", is_competitor=True, wide_map=wide_map)),
                    is_competitor=True,
                )
            ]

        gb["_movement_values"] = gb_values
        gb["_mov_avg"] = movement_average(gb_values)
        gb["mov"] = final_offtake_movement(gb_values)

        # Re-point every known GB Original alias to the exact same final dict.
        for alias in ("GB Original NCP", "GB Original", "GB  Original", "GBOriginal", "gb_original", "gboriginal", "gboriginalncp", _product_lookup_key("GB Original NCP")):
            result["competitors"][alias] = gb

        print(
            "✅ AGG GB Original final:",
            "values=", gb_values,
            "avg=", gb.get("_mov_avg"),
            "mov=", gb.get("mov"),
        )

    # Apply the comparison-row normalization after every raw average and
    # rounded movement is ready. Each row gets exactly one movement 10.
    _apply_offtake_comparison_goal(result)

    for product in RING_PRODUCTS:
        aliases = RING_PRODUCT_ALIASES.get(product, [product])
        metrics = [next((rm.get(alias) for alias in aliases if rm.get(alias) is not None), None) for rm in ring_maps]
        qtys = [to_int(_value(m, "qty_ctn")) or 0 for m in metrics]
        result["ring_pull"][product] = {"total_outlets": sum(1 for q in qtys if q > 0), "qty": sum(qtys)}

    key_issues, suggestions = _latest_manual_summary(all_submissions)
    result["key_issues"] = key_issues[:4]
    result["suggestions"] = suggestions[:4]
    while len(result["key_issues"]) < 4:
        result["key_issues"].append("")
    while len(result["suggestions"]) < 4:
        result["suggestions"].append("")
    return result
