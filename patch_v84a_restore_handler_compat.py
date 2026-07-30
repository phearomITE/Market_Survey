#!/usr/bin/env python3
"""V84A compatibility hotfix.

Restores Telegram /map and /dashboard handlers after V84 replaced handlers.py.
Also prevents startup ImportError for any other handler names imported by
run_bot.py but accidentally removed from handlers.py.

Run from the project root:
    python patch_v84a_restore_handler_compat.py
"""

from __future__ import annotations

import ast
from pathlib import Path
import py_compile
import re


ROOT = Path.cwd()
HANDLERS = ROOT / "app" / "bot" / "handlers.py"
RUN_BOT = ROOT / "app" / "bot" / "run_bot.py"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


if not HANDLERS.exists() or not RUN_BOT.exists():
    fail(
        "Run this patch from /d/Bot/Market_Survey_Git. "
        "Expected app/bot/handlers.py and app/bot/run_bot.py."
    )

source = HANDLERS.read_text(encoding="utf-8")
original = source

# Make InlineKeyboard classes available without changing existing imports.
telegram_import_pattern = re.compile(
    r"^from telegram import (?P<names>[^\n]+)$",
    flags=re.MULTILINE,
)
match = telegram_import_pattern.search(source)
if not match:
    fail("Could not find 'from telegram import ...' in handlers.py")

current_import_names = [
    item.strip() for item in match.group("names").split(",") if item.strip()
]
for required_name in ("InlineKeyboardButton", "InlineKeyboardMarkup"):
    if required_name not in current_import_names:
        current_import_names.append(required_name)

new_import_line = "from telegram import " + ", ".join(current_import_names)
source = source[:match.start()] + new_import_line + source[match.end():]

compat_code = r'''

# ---------------------------------------------------------------------------
# V84A compatibility: public Movement Map and Dashboard Telegram commands.
# ---------------------------------------------------------------------------

def _public_web_page_url(path: str) -> str | None:
    """Build a Railway public URL using the configured access token."""
    base_url = str(
        getattr(settings, "public_app_url", "") or ""
    ).strip().rstrip("/")

    if not base_url:
        return None

    normalized_path = "/" + str(path or "").strip().lstrip("/")
    url = f"{base_url}{normalized_path}"

    token = str(
        getattr(settings, "map_viewer_token", "") or ""
    ).strip()

    if token:
        url = f"{url}?access={token}"

    return url


async def map_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Send buttons for the public movement map and dashboard."""
    map_url = _public_web_page_url("/map")
    dashboard_url = _public_web_page_url("/dashboard")

    if not map_url:
        await update.effective_message.reply_text(
            "❌ PUBLIC_APP_URL is missing in Railway Variables."
        )
        return

    rows = [
        [InlineKeyboardButton("🗺 Open Map", url=map_url)],
    ]

    if dashboard_url:
        rows.append(
            [InlineKeyboardButton("📊 Open Dashboard", url=dashboard_url)]
        )

    await update.effective_message.reply_text(
        "🗺 KB Market Survey Movement Map",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def dashboard_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Send a button for the public dashboard."""
    dashboard_url = _public_web_page_url("/dashboard")
    map_url = _public_web_page_url("/map")

    if not dashboard_url:
        await update.effective_message.reply_text(
            "❌ PUBLIC_APP_URL is missing in Railway Variables."
        )
        return

    rows = [
        [InlineKeyboardButton("📊 Open Dashboard", url=dashboard_url)],
    ]

    if map_url:
        rows.append(
            [InlineKeyboardButton("🗺 Open Map", url=map_url)]
        )

    await update.effective_message.reply_text(
        "📊 KB Market Survey Dashboard",
        reply_markup=InlineKeyboardMarkup(rows),
    )
'''

if "async def map_cmd(" not in source:
    source += compat_code

# Read all names imported from app.bot.handlers by run_bot.py.
run_source = RUN_BOT.read_text(encoding="utf-8")
try:
    run_tree = ast.parse(run_source)
except SyntaxError as exc:
    fail(f"run_bot.py has invalid syntax: {exc}")

imported_handler_names: list[str] = []
for node in run_tree.body:
    if isinstance(node, ast.ImportFrom) and node.module == "app.bot.handlers":
        imported_handler_names.extend(alias.name for alias in node.names)

# Find names actually defined or assigned in the patched handlers source.
try:
    handler_tree = ast.parse(source)
except SyntaxError as exc:
    fail(f"handlers.py became invalid before writing: {exc}")

defined_names: set[str] = set()
for node in handler_tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        defined_names.add(node.name)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                defined_names.add(target.id)

missing_names = sorted(set(imported_handler_names) - defined_names)

# Keep Railway alive if V84 removed another old command handler.
# The fallback is explicit to the Telegram user rather than crashing startup.
if missing_names:
    tuple_literal = repr(tuple(missing_names))
    source += f'''


# V84A startup compatibility for additional handlers removed by V84.
async def _v84_removed_command_fallback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    command_text = str(getattr(message, "text", "") or "").split()
    command_name = command_text[0] if command_text else "This command"
    await message.reply_text(
        f"⚠️ {{command_name}} was removed during the V84 handlers update. "
        "The bot is online, but this older command still needs its service "
        "logic merged back into V84."
    )


for _v84_missing_handler_name in {tuple_literal}:
    globals()[_v84_missing_handler_name] = _v84_removed_command_fallback
'''

backup = HANDLERS.with_suffix(".py.v84a_backup")
backup.write_text(original, encoding="utf-8")
HANDLERS.write_text(source, encoding="utf-8")

py_compile.compile(str(HANDLERS), doraise=True)
py_compile.compile(str(RUN_BOT), doraise=True)

final_tree = ast.parse(HANDLERS.read_text(encoding="utf-8"))
final_defined = {
    node.name
    for node in final_tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
}
required_real = {"map_cmd", "dashboard_cmd"}
if not required_real.issubset(final_defined):
    fail("map_cmd/dashboard_cmd were not installed")

print(f"Patched: {HANDLERS}")
print(f"Backup: {backup}")
print("Python syntax: OK")
print("map_cmd restored: OK")
print("dashboard_cmd restored: OK")

if missing_names:
    print(
        "Additional run_bot imports protected by compatibility fallback: "
        + ", ".join(missing_names)
    )
else:
    print("No additional missing handler imports detected.")
