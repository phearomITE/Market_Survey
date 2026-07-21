"""Export an XLSX workbook to PDF with correct Khmer complex-text shaping.

Run this helper with LibreOffice's system Python environment (normally
``/usr/bin/python3`` on Debian/Ubuntu). The helper starts an isolated headless
LibreOffice process, assigns the Khmer font to the complex-script font property
for every used sheet range, and exports the workbook to PDF.

Why this is needed:
LibreOffice may use an unrelated default CTL font when importing XLSX files.
The Excel workbook still looks correct in Microsoft Excel, but Khmer combining
marks can be detached in the PDF/PNG. Setting ``CharFontNameComplex`` through
UNO fixes the PDF before PyMuPDF creates the PNG.
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.lang import Locale


def _property(name: str, value) -> PropertyValue:
    item = PropertyValue()
    item.Name = name
    item.Value = value
    return item


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _connect(port: int, timeout_seconds: float = 15.0):
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver",
        local_context,
    )
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return resolver.resolve(
                f"uno:socket,host=127.0.0.1,port={port};urp;"
                "StarOffice.ComponentContext"
            )
        except Exception as exc:  # LibreOffice may still be starting.
            last_error = exc
            time.sleep(0.15)
    raise RuntimeError(f"Could not connect to LibreOffice UNO: {last_error}")


def export_pdf(
    xlsx_path: Path,
    pdf_path: Path,
    soffice_path: str,
    khmer_font: str,
) -> None:
    xlsx_path = xlsx_path.resolve()
    pdf_path = pdf_path.resolve()
    if not xlsx_path.exists():
        raise FileNotFoundError(xlsx_path)

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.unlink(missing_ok=True)

    port = _free_port()
    profile_dir = Path(tempfile.mkdtemp(prefix="kb_lo_khmer_"))
    profile_url = profile_dir.resolve().as_uri()
    process: subprocess.Popen[str] | None = None
    document = None

    try:
        process = subprocess.Popen(
            [
                soffice_path,
                f"-env:UserInstallation={profile_url}",
                "--headless",
                "--nologo",
                "--nodefault",
                "--nolockcheck",
                "--norestore",
                "--nofirststartwizard",
                (
                    "--accept=socket,host=127.0.0.1,"
                    f"port={port};urp;StarOffice.ServiceManager"
                ),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        context = _connect(port)
        service_manager = context.ServiceManager
        desktop = service_manager.createInstanceWithContext(
            "com.sun.star.frame.Desktop",
            context,
        )
        document = desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(str(xlsx_path)),
            "_blank",
            0,
            (
                _property("Hidden", True),
                _property("ReadOnly", False),
                _property("UpdateDocMode", 0),
            ),
        )
        if document is None:
            raise RuntimeError(f"LibreOffice could not open {xlsx_path}")

        khmer_locale = Locale()
        khmer_locale.Language = "km"
        khmer_locale.Country = "KH"
        khmer_locale.Variant = ""

        for sheet in document.Sheets:
            cursor = sheet.createCursor()
            cursor.gotoEndOfUsedArea(True)
            # Set the CTL font across the used range first. Latin text keeps its
            # normal font because only the complex-script property is changed.
            cursor.CharFontNameComplex = khmer_font
            cursor.CharLocaleComplex = khmer_locale

            # Reinforce the Khmer font on actual Khmer string cells and remove
            # accidental zero-width spaces before PDF export. This fixes words
            # such as គ្រប់ when LibreOffice imported the XLSX with a bad CTL
            # fallback font.
            address = cursor.RangeAddress
            for row_index in range(address.StartRow, address.EndRow + 1):
                for col_index in range(address.StartColumn, address.EndColumn + 1):
                    cell = sheet.getCellByPosition(col_index, row_index)
                    text_value = getattr(cell, "String", "") or ""
                    if not any("\u1780" <= ch <= "\u17ff" for ch in text_value):
                        continue
                    normalized = unicodedata.normalize("NFC", text_value).replace("\u200b", "")
                    if normalized != text_value:
                        cell.String = normalized
                    cell.CharFontNameComplex = khmer_font
                    cell.CharLocaleComplex = khmer_locale

        document.storeToURL(
            uno.systemPathToFileUrl(str(pdf_path)),
            (
                _property("FilterName", "calc_pdf_Export"),
                _property("Overwrite", True),
            ),
        )
    finally:
        if document is not None:
            try:
                document.close(True)
            except Exception:
                pass
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=8)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        shutil.rmtree(profile_dir, ignore_errors=True)

    if not pdf_path.exists() or pdf_path.stat().st_size <= 0:
        raise RuntimeError(f"LibreOffice did not create {pdf_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx_path")
    parser.add_argument("pdf_path")
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--khmer-font", default="Noto Sans Khmer")
    args = parser.parse_args()

    export_pdf(
        Path(args.xlsx_path),
        Path(args.pdf_path),
        args.soffice,
        args.khmer_font,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
