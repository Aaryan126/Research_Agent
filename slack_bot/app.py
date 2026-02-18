"""Standalone Slack bot entry point (Socket Mode, single workspace).

NOTE: This file is for local development/testing only.
For production with "Add to Slack" OAuth, the bot runs inside FastAPI.
Start the FastAPI server instead:

    uvicorn server.main:app --host 0.0.0.0 --port 8000

See SLACK.md for full details.
"""

import asyncio
import logging
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.chdir(_project_root)

from dotenv import load_dotenv

load_dotenv(os.path.join(_project_root, ".env"))

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from slack_bot.handlers import register_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
register_handlers(app)


async def main():
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("Slack bot starting (Socket Mode)...")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
