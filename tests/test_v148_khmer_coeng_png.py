from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from openpyxl import Workbook

from app.reports.excel_report import _normalize_khmer_cells
from app.services import render_service


def test_full_stock_label_keeps_exact_khmer_cluster():
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "គ្\u200bរប់"

    _normalize_khmer_cells(sheet)

    assert sheet["A1"].value == "គ្រប់"
    assert [ord(char) for char in sheet["A1"].value] == [
        0x1782,
        0x17D2,
        0x179A,
        0x1794,
        0x17CB,
    ]


def test_excel_to_pdf_prefers_khmer_ctl_export_on_linux():
    with TemporaryDirectory() as temporary:
        xlsx_path = Path(temporary) / "report.xlsx"
        xlsx_path.write_bytes(b"test")

        def fake_ctl_export(source: Path, output: Path, soffice: str) -> bool:
            assert source == xlsx_path.resolve()
            assert soffice == "/usr/bin/libreoffice"
            output.write_bytes(b"%PDF-khmer-ctl")
            return True

        with (
            patch.object(
                render_service,
                "_find_soffice",
                return_value="/usr/bin/libreoffice",
            ),
            patch.object(
                render_service,
                "_khmer_font_match",
                return_value=(True, "Noto Sans Khmer|font.ttf"),
            ),
            patch.object(
                render_service,
                "_excel_to_pdf_with_khmer_uno",
                side_effect=fake_ctl_export,
            ) as ctl_export,
        ):
            result = render_service.excel_to_pdf(xlsx_path)

        assert result == xlsx_path.with_suffix(".pdf")
        assert result.read_bytes() == b"%PDF-khmer-ctl"
        ctl_export.assert_called_once()
