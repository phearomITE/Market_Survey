from __future__ import annotations

import asyncio
import os
import signal

import uvicorn

from app.bot.run_bot import _build_application
from app.db.database import init_db


async def _run() -> None:
    init_db()
    port = int(os.getenv("PORT", "8080"))
    server = uvicorn.Server(
        uvicorn.Config("app.main:app", host="0.0.0.0", port=port, log_level="info")
    )
    telegram = _build_application()
    stop = asyncio.Event()

    def request_stop() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            pass

    print(f"🌐 Movement map and dashboard listening on PORT={port}")
    web_task = asyncio.create_task(server.serve())
    try:
        await telegram.initialize()
        await telegram.start()
        if telegram.updater is None:
            raise RuntimeError("Telegram updater is unavailable")
        await telegram.updater.start_polling(drop_pending_updates=False)
        print("✅ KB Market Survey Bot running...")
        stop_task = asyncio.create_task(stop.wait())
        done, _ = await asyncio.wait(
            {web_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if web_task in done and web_task.exception():
            raise web_task.exception()
    finally:
        server.should_exit = True
        if telegram.updater and telegram.updater.running:
            await telegram.updater.stop()
        if telegram.running:
            await telegram.stop()
        await telegram.shutdown()
        await web_task


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
