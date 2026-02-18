"""FastAPI entry point for the Research Review backend."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from server.routers.research import router as research_router
from server.mcp_server import mcp as research_mcp

logging.basicConfig(level=logging.INFO)
logging.getLogger("server").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

# Build the MCP sub-app early so we can wire up its lifespan.
_mcp_http_app = research_mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
    """Run the MCP sub-app's lifespan (initializes its session manager)."""
    async with _mcp_http_app.router.lifespan_context(_mcp_http_app):
        yield


app = FastAPI(title="Research Review Agent API", lifespan=lifespan)

# CORS: allow configured origins + localhost for dev.
# Set ALLOWED_ORIGINS env var as comma-separated list for production,
# e.g. "https://your-app.vercel.app,https://your-domain.com"
_default_origins = ["http://localhost:5173", "http://localhost:3000"]
_extra = os.getenv("ALLOWED_ORIGINS", "")
_origins = _default_origins + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# --- Slack Bot (OAuth / HTTP mode) ---
# Only mount if Slack credentials are configured.
if os.getenv("SLACK_CLIENT_ID") and os.getenv("SLACK_SIGNING_SECRET"):
    from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
    from slack_bot.bolt_app import bolt_app

    _slack_handler = AsyncSlackRequestHandler(bolt_app)

    @app.get("/slack/install")
    async def slack_install(req: Request):
        return await _slack_handler.handle(req)

    @app.get("/slack/oauth_redirect")
    async def slack_oauth_redirect(req: Request):
        return await _slack_handler.handle(req)

    @app.post("/slack/events")
    async def slack_events(req: Request):
        return await _slack_handler.handle(req)

    logger.info("Slack bot routes mounted at /slack/*")
else:
    logger.info("Slack bot disabled (SLACK_CLIENT_ID or SLACK_SIGNING_SECRET not set)")


# Mount LAST — streamable_http_app() creates a route at /mcp internally,
# so mounting at "" makes the full path /mcp (not /mcp/mcp).
app.mount("", _mcp_http_app)
