#!/usr/bin/env python3
"""Convert dealer submission alerts to manual-command-only mode.

Run from the project root. This patch preserves unrelated newer bot features.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path.cwd()
RUN_BOT = ROOT / "app/bot/run_bot.py"
HANDLERS = ROOT / "app/bot/handlers.py"
SERVICE = ROOT / "app/services/submission_alert_service.py"
CONFIG = ROOT / "app/core/config.py"
ENV_EXAMPLE = ROOT / ".env.example"
README = ROOT / "README.md"

for path in (RUN_BOT, HANDLERS, CONFIG):
    if not path.exists():
        raise SystemExit(f"Run from project root. Missing {path}")

SERVICE.parent.mkdir(parents=True, exist_ok=True)

SERVICE_TEXT = '''from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.data.dealers import ALL_DEALERS


FINAL_SUMMARY_KEYWORDS = {
    "បូកសរុបរួម",
    "បូកសរុបរូម",
    "សរុបរួម",
    "បួកសរុបរួម",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\\u200b", "").split()).strip()


def _is_final_summary_outlet_name(value: Any) -> bool:
    normalized = _clean(value).replace(" ", "")
    return normalized in {item.replace(" ", "") for item in FINAL_SUMMARY_KEYWORDS}


def local_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.app_timezone))
    except Exception:
        return datetime.now(ZoneInfo("Asia/Phnom_Penh"))


def dealer_submission_counts(report_date: date) -> dict[str, int]:
    """Count real outlet submissions for all official dealers on one date."""
    from sqlalchemy import select
    from app.db.database import SessionLocal
    from app.db.models import KoboSubmission

    counts: Counter[str] = Counter()
    official = set(ALL_DEALERS)

    with SessionLocal() as db:
        stmt = select(KoboSubmission.dealer, KoboSubmission.outlet_name).where(
            KoboSubmission.report_date == report_date
        )
        for dealer, outlet_name in db.execute(stmt):
            dealer_code = _clean(dealer).upper()
            if dealer_code not in official:
                continue
            if _is_final_summary_outlet_name(outlet_name):
                continue
            counts[dealer_code] += 1

    return {dealer: int(counts.get(dealer, 0)) for dealer in ALL_DEALERS}


def dealers_below_threshold(
    counts: dict[str, int],
    threshold: int,
) -> list[tuple[str, int]]:
    """List low-submit dealers, closest to the target first.

    Example: for <10, a dealer with 8 reports appears before a dealer with 5.
    Official dealer order is used to break equal-count ties.
    """
    order = {dealer: index for index, dealer in enumerate(ALL_DEALERS)}
    rows = [
        (dealer, int(counts.get(dealer, 0)))
        for dealer in ALL_DEALERS
        if int(counts.get(dealer, 0)) < int(threshold)
    ]
    return sorted(rows, key=lambda item: (-item[1], order[item[0]]))


def format_submission_alert(
    report_date: date,
    threshold: int,
    counts: dict[str, int] | None = None,
) -> str:
    counts = counts or dealer_submission_counts(report_date)
    low_dealers = dealers_below_threshold(counts, threshold)

    lines = [
        f"📊 Dealer ដែល Submit Report តិចជាង {threshold}",
        f"📅 {report_date:%d/%m/%Y}",
        "",
    ]

    if low_dealers:
        lines.extend(
            f"{index}. {dealer} = {count} Report"
            for index, (dealer, count) in enumerate(low_dealers, start=1)
        )
        lines.extend(["", f"សរុប Dealer: {len(low_dealers)}"])
    else:
        lines.append(f"✅ Dealer ទាំងអស់បាន Submit ចាប់ពី {threshold} Report ឡើងទៅ។")

    return "\\n".join(lines)
'''
SERVICE.write_text(SERVICE_TEXT, encoding="utf-8")


def remove_functions(source: str, names: set[str]) -> str:
    tree = ast.parse(source)
    spans: list[tuple[int, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            start = node.lineno
            end = node.end_lineno or node.lineno
            spans.append((start, end))
    if not spans:
        return source
    lines = source.splitlines()
    remove_lines: set[int] = set()
    for start, end in spans:
        remove_lines.update(range(start, end + 1))
    result = [line for number, line in enumerate(lines, start=1) if number not in remove_lines]
    return "\n".join(result).rstrip() + "\n"


# ---------------- handlers.py ----------------
handlers = HANDLERS.read_text(encoding="utf-8")

# Remove any previous submission-alert import block.
handlers = re.sub(
    r"\nfrom app\.services\.submission_alert_service import \([\s\S]*?\)\n",
    "\n",
    handlers,
    count=1,
)
handlers = re.sub(
    r"\nfrom app\.services\.submission_alert_service import [^\n]+\n",
    "\n",
    handlers,
    count=1,
)

# Ensure datetime import.
if not re.search(r"^from datetime import .*datetime", handlers, flags=re.M):
    handlers = handlers.replace("import asyncio\n", "import asyncio\nfrom datetime import datetime\n", 1)

# Add manual-only imports.
anchor = "from app.services.render_service import excel_to_png, excel_to_pdf\n"
manual_import = (
    anchor
    + "from app.services.submission_alert_service import (\n"
      "    dealer_submission_counts,\n"
      "    format_submission_alert,\n"
      "    local_now,\n"
      ")\n"
)
if "from app.services.submission_alert_service import" not in handlers:
    if anchor not in handlers:
        raise SystemExit("Could not locate render_service import in handlers.py")
    handlers = handlers.replace(anchor, manual_import, 1)

# Remove old manual functions only, preserving later unrelated functions.
handlers = remove_functions(handlers, {"_parse_alert_submit_args", "alert_submit_cmd"})

manual_functions = r'''

def _parse_alert_submit_args(args: list[str] | tuple[str, ...]):
    """Parse /alert_submit [YYYY-MM-DD] [10|20].

    With no threshold, both <10 and <20 sections are returned.
    """
    report_date = local_now().date()
    threshold: int | None = None

    for raw in args:
        token = str(raw or "").strip()
        if not token:
            continue
        if len(token) == 10 and token[4] == "-" and token[7] == "-":
            try:
                report_date = datetime.strptime(token, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValueError("Date must use YYYY-MM-DD, for example 2026-07-25.") from exc
            continue
        if token.isdigit():
            threshold = int(token)
            continue
        raise ValueError(
            "Usage: /alert_submit, /alert_submit 10, /alert_submit 20, "
            "or /alert_submit 2026-07-25 10"
        )

    if threshold is not None and threshold not in {10, 20}:
        raise ValueError("Threshold must be 10 or 20.")

    thresholds = [threshold] if threshold is not None else [10, 20]
    return report_date, thresholds


async def alert_submit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate dealer submission alerts only when this command is used."""
    try:
        report_date, thresholds = _parse_alert_submit_args(context.args)
    except ValueError as exc:
        await update.effective_message.reply_text(f"❌ {exc}")
        return

    threshold_label = " and ".join(f"<{value}" for value in thresholds)
    wait = await update.effective_message.reply_text(
        f"🔎 Checking dealer submissions for {report_date} ({threshold_label})..."
    )

    try:
        # One database query is reused for both threshold sections.
        counts = await asyncio.to_thread(dealer_submission_counts, report_date)
        sections = [
            format_submission_alert(report_date, threshold, counts)
            for threshold in thresholds
        ]
        # Keep each alert below Telegram's message-size limit. With no argument,
        # edit the waiting message with <10 and send <20 as a second message.
        await wait.edit_text(sections[0])
        for section in sections[1:]:
            await update.effective_message.reply_text(section)
    except Exception as exc:
        await wait.edit_text(f"❌ Submit alert failed: {exc}")
'''
handlers = handlers.rstrip() + manual_functions + "\n"

# Add help text entries without duplicating them.
if "/alert_submit" not in handlers.split('""".strip()', 1)[0]:
    handlers = handlers.replace(
        "/summary 2026-07-05\n/help",
        "/summary 2026-07-05\n/alert_submit\n/alert_submit 10\n/alert_submit 20\n/help",
        1,
    )
if "/alert_submit =" not in handlers:
    handlers = handlers.replace(
        "/summary = generate management summary by Region + Dealer, including 0-submit dealers.\n",
        "/summary = generate management summary by Region + Dealer, including 0-submit dealers.\n"
        "/alert_submit = manually show dealer submission counts; no automatic schedule.\n",
        1,
    )

HANDLERS.write_text(handlers, encoding="utf-8")

# ---------------- run_bot.py ----------------
run_bot = RUN_BOT.read_text(encoding="utf-8")
run_bot = run_bot.replace("from datetime import datetime, timedelta", "from datetime import datetime")

# Remove scheduler-only service import.
run_bot = re.sub(
    r"\nfrom app\.services\.submission_alert_service import \([\s\S]*?\)\n",
    "\n",
    run_bot,
    count=1,
)

# Remove scheduled alert functions while preserving all other functions.
run_bot = remove_functions(
    run_bot,
    {
        "_submit_alert_schedules",
        "_send_scheduled_submit_alert",
        "_submit_alert_loop",
    },
)
run_bot = run_bot.replace("_submit_alert_task: asyncio.Task | None = None\n", "")

# Replace post-init and shutdown with auto-sync-only versions.
run_bot = remove_functions(run_bot, {"_post_init", "_post_shutdown"})
post_functions = '''

async def _post_init(app: Application) -> None:
    global _auto_sync_task
    if settings.auto_sync_enabled:
        _auto_sync_task = asyncio.create_task(_auto_sync_loop())


async def _post_shutdown(app: Application) -> None:
    global _auto_sync_task
    if _auto_sync_task:
        _auto_sync_task.cancel()
        try:
            await _auto_sync_task
        except asyncio.CancelledError:
            pass
'''
# Insert before _safe_database_target.
safe_anchor = "\ndef _safe_database_target() -> str:\n"
if safe_anchor not in run_bot:
    raise SystemExit("Could not locate _safe_database_target in run_bot.py")
run_bot = run_bot.replace(safe_anchor, post_functions + safe_anchor, 1)

# Ensure handler is imported.
import_tuple_start = "from app.bot.handlers import (\n"
if "    alert_submit_cmd,\n" not in run_bot:
    if import_tuple_start not in run_bot:
        raise SystemExit("Could not locate handlers import in run_bot.py")
    run_bot = run_bot.replace(import_tuple_start, import_tuple_start + "    alert_submit_cmd,\n", 1)

# Ensure command is registered.
summary_handler = '    app.add_handler(CommandHandler("summary", summary_cmd))\n'
alert_handler = '    app.add_handler(CommandHandler("alert_submit", alert_submit_cmd))\n'
if alert_handler not in run_bot:
    if summary_handler not in run_bot:
        raise SystemExit("Could not locate summary handler in run_bot.py")
    run_bot = run_bot.replace(summary_handler, summary_handler + alert_handler, 1)

RUN_BOT.write_text(run_bot, encoding="utf-8")

# ---------------- settings/docs ----------------
config = CONFIG.read_text(encoding="utf-8")
config = config.replace("submit_alert_enabled: bool = True", "submit_alert_enabled: bool = False")
CONFIG.write_text(config, encoding="utf-8")

if ENV_EXAMPLE.exists():
    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    env_text = re.sub(r"(?m)^SUBMIT_ALERT_ENABLED=.*$", "SUBMIT_ALERT_ENABLED=false", env_text)
    ENV_EXAMPLE.write_text(env_text, encoding="utf-8")

if README.exists():
    readme = README.read_text(encoding="utf-8")
    note = '''\n\n## Manual dealer submission alert\n\nDealer submission alerts run only when a user sends a command. There is no 9:30 AM or 10:30 AM background schedule.\n\n```text\n/alert_submit                    # today: show both <10 and <20\n/alert_submit 10                 # today: only <10\n/alert_submit 20                 # today: only <20\n/alert_submit 2026-07-25         # selected date: both sections\n/alert_submit 2026-07-25 10      # selected date: only <10\n```\n'''
    if "## Manual dealer submission alert" not in readme:
        readme = readme.rstrip() + note
    README.write_text(readme, encoding="utf-8")

# Validate syntax.
for path in (SERVICE, HANDLERS, RUN_BOT, CONFIG):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("Manual submit-alert patch applied.")
print("Automatic 09:30 and 10:30 scheduler: removed")
print("Manual /alert_submit command: enabled")
print("Python syntax: OK")
