"""Weekly report guidance. The cycle is keyed to the report date."""

from datetime import date, datetime

from openpyxl.styles import Alignment, Font, PatternFill


NO_COMPROMISE = (
    "1.Mass Products មិនត្រូវឲ្យខ្វះស្លកក្នុងផ្ទះមួយ(CBL/Wurkz/Exprez/Dazz/Water/Sport PET 500ml/Ize PET 500ml)",
    "2.ផលិតផលហួសការកំណត់",
    "3. ការបញ្ចូលរបាយការណ៍លក់មិនត្រឹមត្រូវ",
    "4. របាយការណ៍លក់ជូនអតិថិជនមិនពិត (ទាំងចំនួនលក់ និងតម្លៃ)។",
)

# The historical ZIP includes the No Compromise text but no Don't source
# table. These seven points retain the themes visible in the supplied 19 Sep
# screenshot. They live in one place so their exact wording is easy to edit.
DONT = (
    "Do not sell Retail at Wholesale prices.",
    "Do not leave Mass Products unavailable at the outlet.",
    "Do not submit inaccurate product or outlet reports.",
    "Do not start a Program without completing its Build.",
    "Do not leave outlet actions unfinished.",
    "Do not skip the 15-minute Morning Talk.",
    "Do not leave reported outlet issues unresolved.",
)


def guidance_for_date(report_date):
    """12 Sep 2026 = No Compromise, 19 Sep = Don't; repeat weekly."""
    if isinstance(report_date, datetime):
        report_date = report_date.date()
    elif isinstance(report_date, str):
        report_date = next(
            (datetime.strptime(report_date.strip(), fmt).date()
             for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
             if _matches_date(report_date.strip(), fmt)),
            None,
        )
    if not isinstance(report_date, date):
        report_date = date.today()
    weeks = (report_date - date(2026, 9, 12)).days // 7
    return ("No Compromise", NO_COMPROMISE) if weeks % 2 == 0 else ("Don't", DONT)


def _matches_date(value, fmt):
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False


def write_guidance(ws, report_date, header_row):
    """Append the dated guidance below the existing report summaries."""
    title, lines = guidance_for_date(report_date)
    ws.merge_cells(start_row=header_row, start_column=1, end_row=header_row, end_column=27)
    header = ws.cell(header_row, 1)
    header.value = title
    header.fill = PatternFill("solid", fgColor="FF1018")
    header.font = Font(name="Noto Sans Khmer", size=12, bold=True, color="FFFFFF")
    header.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[header_row].height = 26
    for index, line in enumerate(lines, 1):
        row = header_row + index
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=27)
        cell = ws.cell(row, 1)
        cell.value = line if line.lstrip().startswith(f"{index}.") else f"{index}. {line}"
        cell.font = Font(name="Noto Sans Khmer", size=11)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[row].height = 28 if len(line) < 95 else 42
    return header_row + len(lines)
