from __future__ import annotations

import asyncio
import os
import threading

import uvicorn

from app.bot.run_bot import run_bot_async


def _telegram_worker() -> None:
    """Run Telegram in an isolated thread with its own asyncio loop."""
    try:
        asyncio.run(run_bot_async())
    except Exception as exc:
        # The web service must remain available even if Telegram fails.
        print(f"❌ Telegram bot stopped; web map remains available: {exc}")


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    print(f"🌐 Movement map and dashboard listening on PORT={port}")

    telegram_thread = threading.Thread(
        target=_telegram_worker,
        name="telegram-bot",
        daemon=True,
    )
    telegram_thread.start()

    # Keep Uvicorn in the main thread so signal handling works on Railway.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
