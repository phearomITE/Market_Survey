"""CMFB display branding shared by workbook exports."""
from pathlib import Path
from openpyxl.drawing.image import Image
from app.core.config import settings


def add_summary_logo(sheet, *, anchor='A2'):
    folder = settings.template_file.parent
    logo = next((p for p in (folder/'cmfb_logo.png', folder/'kb_logo.png') if p.is_file()), None)
    if logo is None:
        return
    image = Image(str(logo))
    original_width, original_height = image.width, image.height
    image.width = 190
    image.height = 190 * original_height / original_width
    sheet.add_image(image, anchor)
    # Leave the title and date in place; the logo occupies the left of rows 2-3.
    sheet.row_dimensions[2].height = max(sheet.row_dimensions[2].height or 0, 34)
    sheet.row_dimensions[3].height = max(sheet.row_dimensions[3].height or 0, 40)


def brand_summary_workbook(workbook):
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and 'CMFB Market' in cell.value:
                    cell.value = cell.value.replace('CMFB Market', 'CMFB Market')
        # Detail tabs start with data headers in row 1; never overlay their rows.
        if 'Market Survey' in str(sheet['A1'].value or ''):
            add_summary_logo(sheet)
