from copy import copy

from openpyxl import Workbook

from app.reports.excel_report import _prepare_khmer_cells_for_libreoffice


def test_khmer_cells_receive_noto_font():
    workbook = Workbook()
    cell = workbook.active["A1"]
    cell.value = "គ្រប់"
    old_font = copy(cell.font)

    _prepare_khmer_cells_for_libreoffice(workbook)

    assert cell.value == "គ្រប់"
    assert cell.font.name == "Noto Sans Khmer"
    assert cell.font.bold == old_font.bold
