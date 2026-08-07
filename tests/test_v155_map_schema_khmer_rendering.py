from pathlib import Path

from app.db.models import KoboSubmission
from app.reports.excel_report import SUMMARY_FONT_NAME, _normalize_khmer_cells
from openpyxl import Workbook


ROOT = Path(__file__).resolve().parents[1]


def test_map_administrative_columns_exist_on_model_and_migration():
    for name in ("province", "district", "commune", "village"):
        assert hasattr(KoboSubmission, name)

    migration = (ROOT / "app/db/database.py").read_text(encoding="utf-8")
    for name in ("province", "district", "commune", "village"):
        assert f'("{name}", "VARCHAR(160)")' in migration


def test_joined_khmer_word_is_preserved_and_uses_libreoffice_font():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "គ្\u200bរប់"

    _normalize_khmer_cells(sheet)

    assert sheet["A1"].value == "គ្រប់"
    assert sheet["A1"].font.name == "Khmer OS System"
    assert sheet["A1"].font.scheme is None
    assert SUMMARY_FONT_NAME == "Khmer OS System"


def test_railway_image_installs_the_matching_khmer_font():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "fonts-khmeros" in dockerfile
    assert '"Khmer OS System"' in dockerfile
