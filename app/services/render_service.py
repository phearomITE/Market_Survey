from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import threading
import zipfile

from app.core.config import settings


def _find_soffice() -> str | None:
    """Find LibreOffice/soffice on Windows, macOS, or Linux."""
    env_path = settings.libreoffice_path or os.getenv("LIBREOFFICE_PATH") or os.getenv("SOFFICE_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found

    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/snap/bin/libreoffice",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _compact_output(value: str | None, limit: int = 1200) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return "..." + text[-(limit - 3):]


def _is_valid_pdf(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 20:
            return False
        with path.open("rb") as stream:
            return stream.read(5) == b"%PDF-"
    except OSError:
        return False


def _converted_pdf(output_dir: Path, expected_stem: str) -> Path | None:
    expected = output_dir / f"{expected_stem}.pdf"
    if _is_valid_pdf(expected):
        return expected
    candidates = [path for path in output_dir.glob("*.pdf") if _is_valid_pdf(path)]
    return candidates[0] if len(candidates) == 1 else None


def _run_libreoffice_conversion(
    command: list[str],
    environment: dict[str, str],
    output_dir: Path,
    expected_stem: str,
    timeout_seconds: int,
) -> tuple[Path | None, str]:
    for stale in output_dir.glob("*.pdf"):
        try:
            stale.unlink()
        except OSError:
            pass

    try:
        process = subprocess.run(
            command,
            check=False,
            timeout=timeout_seconds,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        return None, f"timed out after {timeout_seconds}s: {_compact_output(exc.stderr or exc.stdout)}"
    except Exception as exc:
        return None, f"could not start LibreOffice: {exc}"

    pdf = _converted_pdf(output_dir, expected_stem)
    output = _compact_output(f"{process.stdout or ''} {process.stderr or ''}")
    if pdf:
        return pdf, output
    return None, f"exit={process.returncode}; {output or 'no PDF file was produced'}"


def excel_to_pdf_with_diagnostics(xlsx_path: Path) -> tuple[Path | None, str | None]:
    """Convert an Excel workbook to PDF and return a useful failure reason.

    Railway safeguards:
    - every conversion uses a private LibreOffice profile (no profile locks)
    - the primary attempt forces LibreOffice's true headless ``svp`` backend
    - Xvfb is used as a fallback if the installed LibreOffice still requests X11
    - conversion output is isolated and copied atomically to the final PDF
    """
    xlsx_path = Path(xlsx_path).resolve()
    if not xlsx_path.is_file():
        return None, f"Excel file not found: {xlsx_path}"

    soffice = _find_soffice()
    if not soffice:
        return None, "LibreOffice/soffice was not found"

    final_pdf = xlsx_path.with_suffix(".pdf")
    timeout_seconds = max(10, int(os.getenv("PNG_RENDER_TIMEOUT_SECONDS", "45")))
    attempts: list[str] = []

    try:
        with tempfile.TemporaryDirectory(prefix="kb-lo-render-") as temporary:
            temporary_dir = Path(temporary)
            output_dir = temporary_dir / "output"
            output_dir.mkdir()

            def build_environment(runtime_dir: Path, use_svp: bool) -> dict[str, str]:
                runtime_dir.mkdir(parents=True, exist_ok=True)
                try:
                    runtime_dir.chmod(0o700)
                except OSError:
                    pass
                environment = os.environ.copy()
                environment["HOME"] = str(temporary_dir)
                environment["TMPDIR"] = str(temporary_dir)
                environment["XDG_RUNTIME_DIR"] = str(runtime_dir)
                environment["LANG"] = environment.get("LANG") or "C.UTF-8"
                environment["LC_ALL"] = environment.get("LC_ALL") or "C.UTF-8"
                if use_svp:
                    environment["SAL_USE_VCLPLUGIN"] = "svp"
                    environment.pop("DISPLAY", None)
                else:
                    environment.pop("SAL_USE_VCLPLUGIN", None)
                return environment

            def libreoffice_args(profile_dir: Path) -> list[str]:
                profile_dir.mkdir(parents=True, exist_ok=True)
                return [
                    soffice,
                    f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
                    "--headless",
                    "--invisible",
                    "--nologo",
                    "--nodefault",
                    "--nolockcheck",
                    "--norestore",
                    "--nofirststartwizard",
                    "--convert-to",
                    "pdf:calc_pdf_Export",
                    "--outdir",
                    str(output_dir),
                    str(xlsx_path),
                ]

            primary_args = libreoffice_args(temporary_dir / "profile-svp")
            pdf, detail = _run_libreoffice_conversion(
                primary_args,
                build_environment(temporary_dir / "runtime-svp", use_svp=True),
                output_dir,
                xlsx_path.stem,
                timeout_seconds,
            )
            if not pdf:
                attempts.append(f"headless svp: {detail}")

                xvfb_run = shutil.which("xvfb-run")
                if xvfb_run:
                    fallback_args = libreoffice_args(temporary_dir / "profile-xvfb")
                    fallback_args = [
                        xvfb_run,
                        "-a",
                        "-s",
                        "-screen 0 1920x1080x24",
                        *fallback_args,
                    ]
                    pdf, detail = _run_libreoffice_conversion(
                        fallback_args,
                        build_environment(temporary_dir / "runtime-xvfb", use_svp=False),
                        output_dir,
                        xlsx_path.stem,
                        timeout_seconds,
                    )
                    if not pdf:
                        attempts.append(f"Xvfb fallback: {detail}")
                else:
                    attempts.append("Xvfb fallback unavailable (xvfb-run not installed)")

            if not pdf:
                reason = " | ".join(attempts)
                print(f"⚠️ PNG renderer PDF conversion failed for {xlsx_path.name}: {reason}")
                return None, reason

            atomic_temp = final_pdf.with_name(
                f".{final_pdf.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            shutil.copyfile(pdf, atomic_temp)
            os.replace(atomic_temp, final_pdf)

        print(f"✅ PNG renderer PDF ready: {final_pdf.name}")
        return final_pdf, None
    except Exception as exc:
        reason = f"LibreOffice conversion setup failed: {exc}"
        print(f"⚠️ PNG renderer failed for {xlsx_path.name}: {reason}")
        return None, reason


def excel_to_pdf(xlsx_path: Path) -> Path | None:
    """Backward-compatible PDF conversion wrapper."""
    pdf, _ = excel_to_pdf_with_diagnostics(Path(xlsx_path))
    return pdf


def _crop_white_border(png_path: Path, padding: int = 35) -> None:
    """Remove large white page margins so Telegram's preview is readable."""
    try:
        from PIL import Image, ImageChops

        with Image.open(png_path) as source:
            image = source.convert("RGB")
        background = Image.new("RGB", image.size, (255, 255, 255))
        bounding_box = ImageChops.difference(image, background).getbbox()
        if not bounding_box:
            return
        left = max(bounding_box[0] - padding, 0)
        top = max(bounding_box[1] - padding, 0)
        right = min(bounding_box[2] + padding, image.width)
        bottom = min(bounding_box[3] + padding, image.height)
        image.crop((left, top, right, bottom)).save(png_path, optimize=True)
    except Exception as exc:
        print(f"⚠️ PNG border crop skipped: {exc}")


def _resize_if_too_wide(png_path: Path, max_width: int = 6000) -> None:
    """Keep PNG readable while preventing oversized Telegram documents."""
    try:
        from PIL import Image

        with Image.open(png_path) as source:
            image = source.convert("RGB")
        if image.width <= max_width:
            return
        ratio = max_width / float(image.width)
        new_size = (max_width, max(1, int(image.height * ratio)))
        image.resize(new_size, Image.Resampling.LANCZOS).save(png_path, optimize=True)
    except Exception as exc:
        print(f"⚠️ PNG resize skipped: {exc}")


def pdf_first_page_to_png_with_diagnostics(
    pdf_path: Path,
    png_path: Path | None = None,
) -> tuple[Path | None, str | None]:
    """Render the first PDF page to PNG with bounded memory and a Poppler fallback."""
    pdf_path = Path(pdf_path).resolve()
    if not _is_valid_pdf(pdf_path):
        return None, f"PDF is missing or invalid: {pdf_path}"

    final_png = Path(png_path or pdf_path.with_suffix(".png")).resolve()
    requested_scale = max(1.0, float(os.getenv("PNG_RENDER_SCALE", "4.0")))
    max_width = max(1000, int(os.getenv("PNG_MAX_WIDTH", "6000")))
    errors: list[str] = []

    try:
        with tempfile.TemporaryDirectory(prefix="kb-png-render-") as temporary:
            temporary_png = Path(temporary) / "preview.png"

            try:
                import fitz  # PyMuPDF

                document = fitz.open(str(pdf_path))
                try:
                    if len(document) == 0:
                        raise ValueError("PDF contains no pages")
                    page = document[0]
                    safe_scale = min(requested_scale, max_width / max(float(page.rect.width), 1.0))
                    safe_scale = max(1.0, safe_scale)
                    pixmap = page.get_pixmap(
                        matrix=fitz.Matrix(safe_scale, safe_scale),
                        alpha=False,
                    )
                    pixmap.save(str(temporary_png))
                finally:
                    document.close()
            except Exception as exc:
                errors.append(f"PyMuPDF: {exc}")

            if not temporary_png.is_file() or temporary_png.stat().st_size == 0:
                pdftoppm = shutil.which("pdftoppm")
                if pdftoppm:
                    prefix = Path(temporary) / "poppler_preview"
                    dpi = max(96, min(432, int(72 * requested_scale)))
                    try:
                        process = subprocess.run(
                            [
                                pdftoppm,
                                "-f",
                                "1",
                                "-l",
                                "1",
                                "-singlefile",
                                "-png",
                                "-r",
                                str(dpi),
                                str(pdf_path),
                                str(prefix),
                            ],
                            check=False,
                            timeout=max(10, int(os.getenv("PNG_RENDER_TIMEOUT_SECONDS", "45"))),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        poppler_png = prefix.with_suffix(".png")
                        if process.returncode == 0 and poppler_png.is_file():
                            shutil.move(poppler_png, temporary_png)
                        else:
                            errors.append(
                                f"pdftoppm exit={process.returncode}: "
                                f"{_compact_output(process.stderr or process.stdout)}"
                            )
                    except Exception as exc:
                        errors.append(f"pdftoppm: {exc}")
                else:
                    errors.append("pdftoppm fallback unavailable")

            if not temporary_png.is_file() or temporary_png.stat().st_size == 0:
                return None, " | ".join(errors)

            _crop_white_border(temporary_png, padding=25)
            _resize_if_too_wide(temporary_png, max_width=max_width)
            final_png.parent.mkdir(parents=True, exist_ok=True)
            atomic_temp = final_png.with_name(
                f".{final_png.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            shutil.copyfile(temporary_png, atomic_temp)
            os.replace(atomic_temp, final_png)

        if final_png.is_file() and final_png.stat().st_size > 0:
            print(f"✅ PNG renderer image ready: {final_png.name} ({final_png.stat().st_size} bytes)")
            return final_png, None
        return None, "PNG file was not created"
    except Exception as exc:
        return None, f"PNG rendering setup failed: {exc}"


def pdf_first_page_to_png(pdf_path: Path, png_path: Path | None = None) -> Path | None:
    """Backward-compatible first-page PNG wrapper."""
    png, _ = pdf_first_page_to_png_with_diagnostics(pdf_path, png_path)
    return png


def excel_to_png_with_diagnostics(xlsx_path: Path) -> tuple[Path | None, str | None]:
    """Create a PNG report preview and retain the exact failure reason."""
    pdf, error = excel_to_pdf_with_diagnostics(Path(xlsx_path))
    if not pdf:
        return None, error
    png, error = pdf_first_page_to_png_with_diagnostics(
        pdf,
        Path(xlsx_path).with_suffix(".png"),
    )
    if not png:
        reason = error or "unknown PDF-to-PNG failure"
        print(f"⚠️ PNG renderer rasterization failed for {Path(xlsx_path).name}: {reason}")
        return None, reason
    return png, None


def excel_to_png(xlsx_path: Path) -> Path | None:
    """Backward-compatible Excel-to-PNG wrapper."""
    png, _ = excel_to_png_with_diagnostics(Path(xlsx_path))
    return png


def excel_workbook_to_png_zip(
    xlsx_path: Path,
    sheet_names: list[str] | None = None,
    zip_path: Path | None = None,
) -> Path | None:
    """Render every PDF page from an Excel workbook into one PNG ZIP."""
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        return None

    pdf, error = excel_to_pdf_with_diagnostics(xlsx_path)
    if not pdf:
        print(f"⚠️ Excel workbook PDF conversion failed: {error}")
        return None

    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        print(f"⚠️ Excel workbook PNG ZIP needs PyMuPDF: {exc}")
        return None

    out_dir = xlsx_path.parent / f"{xlsx_path.stem}_png"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_path or xlsx_path.with_name(f"{xlsx_path.stem}_PNG_65_Dealers.zip")

    try:
        for old in out_dir.glob("*.png"):
            try:
                old.unlink()
            except OSError:
                pass

        requested_scale = max(1.0, float(os.getenv("PNG_RENDER_SCALE", "4.0")))
        max_width = max(1000, int(os.getenv("PNG_MAX_WIDTH", "6000")))
        document = fitz.open(str(pdf))
        png_files: list[Path] = []

        try:
            for index, page in enumerate(document):
                if sheet_names and index < len(sheet_names):
                    base_name = "".join(
                        char if char.isalnum() or char in "-_" else "_"
                        for char in str(sheet_names[index])
                    )
                    base_name = base_name.strip("_") or f"dealer_{index + 1:02d}"
                else:
                    base_name = f"dealer_{index + 1:02d}"

                png_path = out_dir / f"{index + 1:02d}_{base_name}.png"
                safe_scale = min(requested_scale, max_width / max(float(page.rect.width), 1.0))
                safe_scale = max(1.0, safe_scale)
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(safe_scale, safe_scale),
                    alpha=False,
                )
                pixmap.save(str(png_path))
                _crop_white_border(png_path, padding=25)
                _resize_if_too_wide(png_path, max_width=max_width)
                if png_path.exists() and png_path.stat().st_size > 0:
                    png_files.append(png_path)
        finally:
            document.close()

        if not png_files:
            return None

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in png_files:
                archive.write(file, arcname=file.name)

        return zip_path if zip_path.exists() and zip_path.stat().st_size > 0 else None
    except Exception as exc:
        print(f"⚠️ Excel workbook PNG ZIP failed: {exc}")
        return None
