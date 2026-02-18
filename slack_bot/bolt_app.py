"""Slack Bolt app with OAuth for multi-workspace distribution."""

import os

from slack_bolt.async_app import AsyncApp
from slack_bolt.oauth.async_oauth_settings import AsyncOAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore

from slack_bot.handlers import register_handlers

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_data_dir = os.path.join(_project_root, "data")

bolt_app = AsyncApp(
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
    oauth_settings=AsyncOAuthSettings(
        client_id=os.environ.get("SLACK_CLIENT_ID", ""),
        client_secret=os.environ.get("SLACK_CLIENT_SECRET", ""),
        scopes=["commands", "chat:write"],
        installation_store=FileInstallationStore(
            base_dir=os.path.join(_data_dir, "installations"),
        ),
        state_store=FileOAuthStateStore(
            expiration_seconds=600,
            base_dir=os.path.join(_data_dir, "states"),
        ),
        install_path="/slack/install",
        redirect_uri_path="/slack/oauth_redirect",
    ),
)

register_handlers(bolt_app)
