"""Verify complete product rename:
EXPREZ Can 500ml ORD -> EXPREZ Can ORD
EXPREZ Can 500ml NCP -> EXPREZ Can NCP
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import date
import openpyxl

ROOT = Path(__file__).resolve().parent

# 1. Check XLSForms
xlsforms = [
    ROOT / "templates/CMFB_Market_Improvement_XLSForm_GT_HORECA.xlsx",
    ROOT / "templates/KB_Market_Improvement_XLSForm_GT_HORECA.xlsx",
    ROOT / "templates/KB_Market_Improvement_XLSForm.xlsx",
]
for xf in xlsforms:
    wb = openpyxl.load_workbook(xf, data_only=False)
    ws = wb["survey"]
    survey_text = [str(cell.value) for row in ws.iter_rows() for cell in row if cell.value]
    full_str = " ".join(survey_text)
    assert "EXPREZ Can ORD" in full_str, f"Missing EXPREZ Can ORD in {xf.name}"
    assert "EXPREZ Can NCP" in full_str, f"Missing EXPREZ Can NCP in {xf.name}"
    assert "EXPREZ Can 500ml ORD" not in full_str, f"Found stale EXPREZ Can 500ml ORD in {xf.name}"
    assert "EXPREZ Can 500ml NCP" not in full_str, f"Found stale EXPREZ Can 500ml NCP in {xf.name}"
print("✅ XLSForms verified: new names present, old 500ml names removed.")

# 2. Check Report Templates
general_tmpl = ROOT / "templates/template_general.xlsx"
wb_gen = openpyxl.load_workbook(general_tmpl, data_only=False)
ws_gen = wb_gen.worksheets[0]
assert ws_gen["B20"].value == "EXPREZ Can ORD", f"B20 is {ws_gen['B20'].value}"
assert ws_gen["B28"].value == "EXPREZ Can NCP", f"B28 is {ws_gen['B28'].value}"
assert ws_gen["H44"].value == "EXPREZ Can ORD", f"H44 is {ws_gen['H44'].value}"

horeca_tmpl = ROOT / "templates/template_horeca_products.xlsx"
if horeca_tmpl.exists():
    wb_hor = openpyxl.load_workbook(horeca_tmpl, data_only=False)
    ws_hor = wb_hor.worksheets[0]
    hor_text = " ".join(str(cell.value) for row in ws_hor.iter_rows() for cell in row if cell.value)
    assert "EXPREZ Can ORD" in hor_text, "Missing EXPREZ Can ORD in template_horeca_products.xlsx"
    assert "EXPREZ Can 500ml" not in hor_text, "Found EXPREZ Can 500ml in template_horeca_products.xlsx"
print("✅ Report templates verified: cells B20, B28, H44 correctly contain EXPREZ Can ORD/NCP.")

# 3. Check Aggregator
from app.reports.aggregator import (
    OWN_PRODUCTS,
    COMPETITOR_PRODUCTS,
    OFFTAKE_COMPARE_GROUPS,
    PRODUCT_CODES,
    PRODUCT_LABEL_ALIASES,
    _canonical_product_name,
)

assert "EXPREZ Can ORD" in OWN_PRODUCTS, "Missing EXPREZ Can ORD in OWN_PRODUCTS"
assert "EXPREZ Can NCP" in OWN_PRODUCTS, "Missing EXPREZ Can NCP in OWN_PRODUCTS"
assert "EXPREZ Can 500ml ORD" not in OWN_PRODUCTS, "Old name still in OWN_PRODUCTS"
assert "EXPREZ Can 500ml NCP" not in OWN_PRODUCTS, "Old name still in OWN_PRODUCTS"

assert "EXPREZ Can ORD" in COMPETITOR_PRODUCTS, "Missing EXPREZ Can ORD in COMPETITOR_PRODUCTS"
assert "EXPREZ Can 500ml ORD" not in COMPETITOR_PRODUCTS, "Old name still in COMPETITOR_PRODUCTS"

group_matches = [g for g in OFFTAKE_COMPARE_GROUPS if "EXPREZ Can ORD" in g]
assert len(group_matches) == 1, f"Expected 1 compare group with EXPREZ Can ORD, got {group_matches}"
assert "EXPREZ Melon ORD" in group_matches[0], "EXPREZ Melon ORD not in same compare group"

assert "EXPREZ Can ORD" in PRODUCT_CODES, "Missing EXPREZ Can ORD in PRODUCT_CODES"
assert "EXPREZ Can NCP" in PRODUCT_CODES, "Missing EXPREZ Can NCP in PRODUCT_CODES"

assert "EXPREZ Can ORD" in PRODUCT_LABEL_ALIASES, "Missing EXPREZ Can ORD in PRODUCT_LABEL_ALIASES"
assert "EXPREZ Can NCP" in PRODUCT_LABEL_ALIASES, "Missing EXPREZ Can NCP in PRODUCT_LABEL_ALIASES"

# 4. Check canonicalization
for input_name in [
    "EXPREZ Can ORD",
    "EXPREZ Can 500ml ORD",
    "EXPREZ Can 330ml ORD",
    "exprez can ord",
    "exprez can 500ml ord",
    "exprez can 330ml ord",
]:
    canonical = _canonical_product_name(input_name)
    assert canonical == "EXPREZ Can ORD", f"Failed canonical for {input_name}: got {canonical}"

for input_name in [
    "EXPREZ Can NCP",
    "EXPREZ Can 500ml NCP",
    "EXPREZ Can 330ml NCP",
    "exprez can ncp",
    "exprez can 500ml ncp",
    "exprez can 330ml ncp",
]:
    canonical = _canonical_product_name(input_name)
    assert canonical == "EXPREZ Can NCP", f"Failed canonical for {input_name}: got {canonical}"
print("✅ Aggregator and Canonicalization verified.")

# 5. Check Excel Report name mapping
from app.reports.excel_report import _product_key, PRODUCT_NAME_MAP

assert _product_key("EXPREZ Can ORD") == "EXPREZ Can ORD"
assert _product_key("EXPREZ Can NCP") == "EXPREZ Can NCP"
assert _product_key("EXPREZ Can 500ml ORD") == "EXPREZ Can ORD"
assert _product_key("EXPREZ Can 500ml NCP") == "EXPREZ Can NCP"
assert _product_key("EXPREZ Can 330ml ORD") == "EXPREZ Can ORD"
assert _product_key("EXPREZ Can 330ml NCP") == "EXPREZ Can NCP"
print("✅ Excel report product key mapping verified.")

# 6. Check Volume Summary
from app.reports.volume_summary import VOLUME_PRODUCTS
assert "EXPREZ Can NCP" in VOLUME_PRODUCTS, "Missing EXPREZ Can NCP in VOLUME_PRODUCTS"
assert "EXPREZ Can 500ml NCP" not in VOLUME_PRODUCTS, "Old name in VOLUME_PRODUCTS"
print("✅ Volume summary products verified.")

# 7. Check Data Export aliases
from app.reports.data_export import PRODUCT_LOOKUP_ALIASES
assert "EXPREZ Can ORD" in PRODUCT_LOOKUP_ALIASES
assert "EXPREZ Can NCP" in PRODUCT_LOOKUP_ALIASES
print("✅ Data export aliases verified.")

# 8. Check Web Router categories
from app.web.router import PRODUCT_CATEGORIES
assert PRODUCT_CATEGORIES.get("EXPREZ Can ORD") == "Beverage"
assert PRODUCT_CATEGORIES.get("EXPREZ Can NCP") == "Beverage"
print("✅ Web router categories verified.")

# 9. Check SQL migration script
migration_sql = (ROOT / "scripts/migrate_exprez_can_rename.sql").read_text(encoding="utf-8")
assert "EXPREZ Can ORD" in migration_sql
assert "EXPREZ Can NCP" in migration_sql
assert "UPDATE kobo_product_metrics" in migration_sql
assert "UPDATE kobo_competitor_metrics" in migration_sql
print("✅ SQL migration script verified.")

print("\n🎉 ALL CHECKS PASSED: EXPREZ Can ORD and EXPREZ Can NCP are fully updated and verified!")
