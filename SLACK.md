# Slack Bot — Research Agent

## Overview

A Slack bot that lets users run AI-powered literature reviews and claim verifications directly from Slack via the `/research` and `/check-claim` slash commands. The bot runs inside the FastAPI server using **HTTP mode with OAuth**, so anyone can install it to their workspace via an "Add to Slack" link.

```
[Any Slack Workspace]
       |
       | HTTPS (slash commands via HTTP POST)
       v
[FastAPI Server]  ── server/main.py (includes Slack routes)
       |               /slack/install         (Add to Slack page)
       |               /slack/oauth_redirect  (OAuth callback)
       |               /slack/events          (slash commands)
       |
       | Direct import (same process)
       v
[Orchestrator]  ── server/services/orchestrator.py
       |
       | HTTPS
       v
[Elastic Cloud]  ── Agent Builder (Research + Peer Review agents)
```

Per-workspace tokens are stored automatically via `FileInstallationStore`.

---

## File Structure

```
slack_bot/
├── __init__.py       # Package init (empty)
├── bolt_app.py       # AsyncApp with OAuth settings (production)
├── app.py            # Standalone Socket Mode entry point (local dev only)
├── handlers.py       # /research + /check-claim command handlers + progress streaming
└── formatting.py     # Markdown → Slack mrkdwn conversion, message splitting
```

---

## Slack App Setup (one-time)

### Step 1: Create the Slack App

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. Name: `Research Agent` (or any name)
4. Pick your workspace
5. Click **Create App**

### Step 2: Note Your App Credentials

In **Basic Information** (left sidebar), scroll to **App Credentials** and note:
- **Client ID** → `SLACK_CLIENT_ID`
- **Client Secret** → `SLACK_CLIENT_SECRET`
- **Signing Secret** → `SLACK_SIGNING_SECRET`

### Step 3: Add Bot Scopes

1. In the left sidebar, click **OAuth & Permissions**
2. Scroll to **Bot Token Scopes** and add:
   - `chat:write` (send and update messages)
   - `commands` (receive slash commands)
3. Under **Redirect URLs**, add:
   ```
   https://elasticresearchagent.duckdns.org/slack/oauth_redirect
   ```

### Step 4: Create the Slash Commands

1. In the left sidebar, click **Slash Commands**
2. Click **Create New Command**:
   - Command: `/research`
   - Request URL: `https://elasticresearchagent.duckdns.org/slack/events`
   - Short Description: `Run an AI literature review on a research topic`
   - Usage Hint: `topic to research`
3. Click **Save**
4. Click **Create New Command** again:
   - Command: `/check-claim`
   - Request URL: `https://elasticresearchagent.duckdns.org/slack/events`
   - Short Description: `Verify a claim against research literature`
   - Usage Hint: `claim to verify`
5. Click **Save**

### Step 5: Disable Socket Mode

1. In the left sidebar, click **Socket Mode**
2. Toggle **Enable Socket Mode** OFF

### Step 6: Enable Distribution

1. In the left sidebar, click **Manage Distribution**
2. Complete all checklist items
3. Click **Activate Public Distribution**

### Step 7: Install to Your Workspace

Visit: `https://elasticresearchagent.duckdns.org/slack/install`

This is the same link you share with anyone who wants to add the bot.

---

## Environment Variables

Add to `.env` on the server:

```env
# Slack Bot (OAuth / HTTP mode)
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret
SLACK_SIGNING_SECRET=your-signing-secret
```

These are in addition to the existing `KIBANA_URL` and `ELASTIC_API_KEY` variables.

If these variables are not set, the Slack routes are simply not mounted — the rest of the server (frontend API, MCP) works normally.

---

## Running

The Slack bot runs inside the FastAPI server — no separate process needed:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

You should see in the logs:

```
INFO: Slack bot routes mounted at /slack/*
```

### Local Development (Socket Mode)

For local testing without deploying, you can still use the standalone Socket Mode entry point. This requires `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` in `.env` and Socket Mode enabled in the app settings:

```bash
python -m slack_bot.app
```

---

## Add to Slack

Share this link with anyone who wants to install the bot:

```
https://elasticresearchagent.duckdns.org/slack/install
```

They click the link, authorize the bot in their workspace, and `/research` and `/check-claim` work immediately.

---

## Dependencies

```
slack-bolt>=1.21.0
slack-sdk>=3.33.0
aiohttp>=3.9.0
```

Already included in `requirements.txt`.

---

## UX Flow

### `/research <topic>`

When a user types `/research hallucination in multi-agent systems`:

1. **Immediate** — Ephemeral acknowledgment: "Starting research on: *hallucination in multi-agent systems*"
2. **Channel message** — ":mag: Research Agent is working on: _topic_" (thread parent)
3. **Thread: progress message** — Updated in-place as events arrive:
   - ":hourglass_flowing_sand: Research Agent starting (iteration 1)..."
   - ":wrench: Using tool: `search_papers`"
   - ":white_check_mark: Research Agent finished."
   - ":hourglass_flowing_sand: Peer Review Agent starting (iteration 1)..."
   - ":white_check_mark: Peer Review Agent finished."
   - ":white_check_mark: Peer Review Verdict (iteration 1): `PASS`"
   - ":white_check_mark: Research complete!"
4. **Thread: full report** — Posted as one or more threaded replies (split at ~3900 chars)
5. **Parent updated** — ":white_check_mark: Research complete: _topic_ — See thread for full report"

### `/check-claim <claim>`

When a user types `/check-claim Multi-agent systems outperform single agents`:

1. **Immediate** — Ephemeral acknowledgment: "Starting claim verification: *claim*"
2. **Channel message** — ":mag: Claim Verification Agent is evaluating: _claim_" (thread parent)
3. **Thread: progress message** — Updated in-place as events arrive:
   - ":hourglass_flowing_sand: Claim Verification Agent starting..."
   - ":wrench: Using tool: `search_papers`"
   - ":white_check_mark: Claim Verification Agent finished."
   - ":white_check_mark: Verification complete!"
4. **Thread: full report** — Posted as one or more threaded replies (split at ~3900 chars)
5. **Parent updated** — ":white_check_mark: Verification complete: _claim_ — See thread for full report"

---

## How It Works

### OAuth Flow

When someone clicks "Add to Slack":
1. `/slack/install` redirects them to Slack's OAuth authorization page
2. They authorize the bot for their workspace
3. Slack redirects back to `/slack/oauth_redirect` with an auth code
4. Bolt exchanges the code for a bot token and stores it in `data/installations/`
5. Future `/research` commands from that workspace use the stored token

### Background Tasks

Research takes 2-8 minutes but Slack requires a response within 3 seconds. The handler calls `ack()` immediately, then spawns the research as a background `asyncio.Task`. The Slack `client` and `respond` objects work independently of the HTTP connection.

### SSE Event Mapping

The bot consumes the same SSE event stream as the web frontend and MCP server:

| SSE Event | Slack Action |
|---|---|
| `agent_start` | Append ":hourglass_flowing_sand: Agent starting..." to progress message |
| `tool_call` | Append ":wrench: Using tool: `tool_id`" |
| `agent_end` | Append ":white_check_mark: Agent finished." |
| `verdict` | Append verdict with PASS/REVISION emoji |
| `result` | Capture report text for posting |
| `error` | Append ":x: Error: message" |
| `reasoning`, `message_chunk` | Skipped (too verbose for Slack) |

### Message Formatting

Reports are Markdown. The `formatting.py` module converts to Slack mrkdwn:

- `## Header` → `*Header*`
- `**bold**` → `*bold*`
- `[text](url)` → `<url|text>`
- Code blocks preserved as-is

Long reports are split at paragraph boundaries (~3900 chars per message).

---

## Costs

| Resource | Cost |
|---|---|
| Slack free tier | **$0** |
| OAuth / HTTP mode | **$0** |
| Runs on existing GCP VM | **$0 extra** |
| **Total** | **$0** |

---

## Troubleshooting

### "Slack bot disabled" in server logs

The `SLACK_CLIENT_ID` or `SLACK_SIGNING_SECRET` environment variables are not set. Add them to `.env` and restart the server.

### Bot not responding to `/research` or `/check-claim`

1. Check the server logs for errors
2. Verify the slash command Request URL is set to `https://elasticresearchagent.duckdns.org/slack/events`
3. Verify Socket Mode is **OFF** in the Slack app settings

### "missing_scope" error

Go to **OAuth & Permissions** and verify `chat:write` and `commands` scopes are added. Users may need to reinstall the app.

### OAuth redirect fails

Verify the Redirect URL in **OAuth & Permissions** matches exactly: `https://elasticresearchagent.duckdns.org/slack/oauth_redirect`

### Research fails with timeout

The orchestrator has a 600-second timeout per agent call. Check the server logs for the specific error.

### Bot works but no report appears

Check the server logs for errors during `run_research_loop`. The most common issue is invalid or expired `ELASTIC_API_KEY` in `.env`.
