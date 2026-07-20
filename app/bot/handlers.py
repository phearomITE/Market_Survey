from __future__ import annotations

import asyncio

from telegram import Update, InputFile
from telegram.ext import ContextTypes

from app.core.config import settings
from app.db.database import init_db
from app.kobo.sync import sync_kobo
from app.services.report_service import (
    generate_data_export,
    generate_dealer_report,
    generate_multi_dealer_reports,
    generate_today_all_dealers_with_pngs,
    generate_region_dealer_summary,
    parse_multi_report_command_args,
    parse_report_command_args,
)
from app.services.render_service import excel_to_png, excel_to_pdf

HELP_TEXT = """
✅ KB Market Survey Bot

Commands:
/start
/sync_kobo
/debug_kobo
/status
/report KRG7 2026-06-06
/report_multi CPH2 CA2 KDL1 CA1 CA7 2026-07-14
/report_today
/report_today 2026-06-06
/summary 2026-07-05
/export 2026-07-18
/help

/report = generate one dealer report and send large PNG file preview first, then Excel only.
/report_multi = generate one workbook with selected dealer sheets + one PNG preview ZIP.
/report_today = generate one Excel workbook with 65 dealer sheets + PNG ZIP for 65 dealer previews.
/summary = generate management summary by Region + Dealer, including 0-submit dealers.
/export = export Summary_Data + Location_Outlet using the approved Excel template.

Logic:
1 Kobo submission = 1 outlet visit
Group by Dealer + Date = 1 dealer template
Auto-sync: bot polls Kobo every 1 minute when AUTO_SYNC_ENABLED=true
""".strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    await update.effective_message.reply_text(HELP_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(HELP_TEXT)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    getter = context.application.bot_data.get("get_last_auto_sync")
    last = getter() if callable(getter) else None
    if not last:
        await update.effective_message.reply_text(
            "ℹ️ Bot is running.\nAuto-sync status: not run yet.\nUse /sync_kobo to sync now or wait for the 1-minute polling."
        )
        return

    t = last.get("time")
    if last.get("error"):
        await update.effective_message.reply_text(f"⚠️ Last auto-sync: {t}\nError: {last['error']}")
        return

    result = last.get("result") or {}
    await update.effective_message.reply_text(
        "✅ Bot is running.\n"
        f"Last auto-sync: {t}\n"
        f"Fetched: {result.get('fetched', 0)} | Synced: {result.get('synced', 0)} | Skipped: {result.get('skipped', 0)}"
    )


async def sync_kobo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("🔄 Syncing Kobo submissions...")
    try:
        result = await asyncio.to_thread(sync_kobo)
        await msg.edit_text(f"✅ Kobo sync completed. Fetched: {result.get('fetched', 0)} | Matched: {result.get('matched', 0)} | Synced: {result.get('synced', 0)} | Hash initialized: {result.get('hash_backfilled', 0)} | Unchanged: {result.get('unchanged', 0)} | Skipped: {result.get('skipped', 0)}")
    except Exception as e:
        await msg.edit_text(f"❌ Kobo sync failed: {e}")


async def _maybe_sync_before_report(message) -> None:
    if not settings.auto_sync_before_report:
        return
    await message.reply_text("🔄 Auto-syncing Kobo first...")
    result = await asyncio.to_thread(sync_kobo)
    await message.reply_text(f"✅ Kobo sync completed. Synced: {result['synced']} | Skipped: {result.get('skipped', 0)}")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage:\n"
            "/report PVH3 2026-07-07\n"
            "/report PVH3 CHANNEL SPECIALIST 2026-07-07"
        )
        return

    try:
        dealer, rdate, report_type = parse_report_command_args(context.args)
    except ValueError as exc:
        await update.effective_message.reply_text(f"❌ {exc}")
        return

    report_label = "CHANNEL SPECIALIST" if report_type == "CHANNEL_SPECIALIST" else "GENERAL"
    wait = await update.effective_message.reply_text(
        f"📊 Generating {report_label} template preview for {dealer} {rdate}..."
    )
    try:
        await _maybe_sync_before_report(update.effective_message)
        path, text = await asyncio.to_thread(generate_dealer_report, dealer, rdate, report_type)
        if not path:
            await wait.edit_text(f"⚠️ {text}")
            return

        await wait.edit_text(f"✅ {text}\n🖼 Creating PNG preview...")

        png = await asyncio.to_thread(excel_to_png, path)
        if png:
            # Send PNG as document, not photo. This keeps full resolution and shows
            # a small preview thumbnail in Telegram, like the user's requested example.
            with png.open("rb") as f:
                await update.effective_message.reply_document(
                    document=InputFile(f, filename=png.name),
                    caption=f"🖼 {dealer} {report_label} {rdate} report preview"
                )
        else:
            await update.effective_message.reply_text(
                "⚠️ PNG preview not created. Install LibreOffice or set LIBREOFFICE_PATH/SOFFICE_PATH. Sending Excel only."
            )

        with path.open("rb") as f:
            await update.effective_message.reply_document(document=InputFile(f, filename=path.name))
    except Exception as e:
        await wait.edit_text(f"❌ Report failed: {e}")



async def report_multi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dealers, rdate = parse_multi_report_command_args(context.args)
    except ValueError as exc:
        await update.effective_message.reply_text(f"❌ {exc}")
        return

    dealer_text = ", ".join(dealers)
    wait = await update.effective_message.reply_text(
        f"📊 Generating selected dealer reports for {rdate}...\n"
        f"Dealers ({len(dealers)}): {dealer_text}"
    )
    try:
        path, png_zip, text = await asyncio.to_thread(
            generate_multi_dealer_reports,
            dealers,
            rdate,
            "GENERAL",
        )

        await wait.edit_text(f"✅ {text}\n📎 Uploading Excel workbook...")
        with path.open("rb") as f:
            await update.effective_message.reply_document(
                document=InputFile(f, filename=path.name),
                caption=f"📊 Selected dealer reports - {dealer_text} ({rdate})",
            )

        if png_zip:
            await update.effective_message.reply_text("🖼 Uploading selected dealer PNG previews...")
            with png_zip.open("rb") as f:
                await update.effective_message.reply_document(
                    document=InputFile(f, filename=png_zip.name),
                    caption=f"🖼 PNG previews - {dealer_text} ({rdate})",
                )
        else:
            await update.effective_message.reply_text(
                "⚠️ Excel was generated, but PNG previews were not created. "
                "Check LibreOffice, PyMuPDF and LIBREOFFICE_PATH."
            )
    except Exception as exc:
        await wait.edit_text(f"❌ Multi-dealer report failed: {exc}")


async def report_today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rdate = context.args[0].strip() if context.args else None
    wait = await update.effective_message.reply_text(
        "📊 Generating /report_today output...\n"
        "Excel workbook: 65 dealer sheets\n"
        "PNG ZIP: 65 dealer previews"
    )
    try:
        await _maybe_sync_before_report(update.effective_message)
        path, png_zip, text = await asyncio.to_thread(generate_today_all_dealers_with_pngs, rdate)

        await wait.edit_text(f"✅ {text}\n📎 Uploading Excel workbook...")
        with path.open("rb") as f:
            await update.effective_message.reply_document(
                document=InputFile(f, filename=path.name),
                caption=f"📊 Excel workbook - 65 dealer sheets ({rdate or 'today'})",
            )

        if png_zip:
            await update.effective_message.reply_text("🖼 Uploading PNG ZIP for 65 dealer previews...")
            with png_zip.open("rb") as f:
                await update.effective_message.reply_document(
                    document=InputFile(f, filename=png_zip.name),
                    caption=f"🖼 PNG previews - 65 dealers ({rdate or 'today'})",
                )
        else:
            await update.effective_message.reply_text(
                "⚠️ PNG ZIP not created. Excel workbook was generated successfully. "
                "Install LibreOffice and PyMuPDF, or set LIBREOFFICE_PATH in .env."
            )
    except Exception as e:
        await wait.edit_text(f"❌ Report today failed: {e}")


async def debug_kobo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.effective_message.reply_text("🔎 Checking Kobo fields...")
    try:
        from app.kobo.client import KoboClient
        from app.kobo.parser import normalize_submission
        rows = KoboClient().fetch_submissions()
        if not rows:
            await msg.edit_text("⚠️ Kobo API returned 0 submissions.")
            return
        data = normalize_submission(rows[0])
        text = (
            f"✅ Kobo rows fetched: {len(rows)}\n"
            f"First normalized row:\n"
            f"region={data.get('region')}\n"
            f"dealer={data.get('dealer')}\n"
            f"report_date={data.get('report_date')}\n"
            f"outlet_name={data.get('outlet_name')}\n"
            f"outlet_type={data.get('outlet_type')}\n"
            f"key_issue={'YES' if data.get('key_issue_text') else 'NO'} | suggestion={'YES' if data.get('suggestion_text') else 'NO'}"
        )
        await msg.edit_text(text)
    except Exception as e:
        await msg.edit_text(f"❌ Debug Kobo failed: {e}")

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /summary 2026-07-05")
        return

    rdate = context.args[0].strip()
    wait = await update.effective_message.reply_text(f"📊 Generating Region/Dealer summary for {rdate}...")
    try:
        await _maybe_sync_before_report(update.effective_message)
        path, text = await asyncio.to_thread(generate_region_dealer_summary, rdate)
        await wait.edit_text(f"✅ {text}\n📎 Uploading summary Excel...")
        with path.open("rb") as f:
            await update.effective_message.reply_document(document=InputFile(f, filename=path.name))
    except Exception as e:
        await wait.edit_text(f"❌ Summary failed: {e}")

async def export_data_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.effective_message.reply_text("Usage: /export 2026-07-18")
        return

    rdate = context.args[0].strip()
    wait = await update.effective_message.reply_text(
        f"📤 Exporting Summary_Data and Location_Outlet for {rdate}..."
    )
    try:
        path, text = await asyncio.to_thread(generate_data_export, rdate)
        if not path:
            await wait.edit_text(f"⚠️ {text}")
            return

        await wait.edit_text(f"✅ {text}\n📎 Uploading data export...")
        with path.open("rb") as file_obj:
            await update.effective_message.reply_document(
                document=InputFile(file_obj, filename=path.name),
                caption=f"📤 Market survey data export ({rdate})",
            )
    except ValueError as exc:
        await wait.edit_text(f"❌ Invalid export date: {exc}")
    except Exception as exc:
        await wait.edit_text(f"❌ Export failed: {exc}")

