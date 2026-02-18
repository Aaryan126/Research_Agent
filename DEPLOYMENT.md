# Deployment Guide — Research Literature Review Agent

## Architecture

```
[Netlify]  ── React/Vite frontend (static site)
       |          https://elasticresearchagent.netlify.app
       |
       | HTTPS (SSE streaming)
       v
[Caddy]  ── Reverse proxy with auto HTTPS (Let's Encrypt)
       |          https://elasticresearchagent.duckdns.org
       |
       | localhost:8000
       v
[Google Cloud VM]  ── FastAPI backend (e2-micro, us-central1)
       |          IP: 34.45.235.139
       |--- /api/health    (Health check)
       |--- /api/research  (REST API — SSE streaming)
       |--- /mcp           (MCP endpoint for Claude Desktop)
       |
       v
[Elastic Cloud]  ── Agent Builder (Research + Peer Review agents)
```

---

## Google Cloud VM Details

| Field | Value |
|---|---|
| **Project** | research-agent |
| **VM Name** | research-agent |
| **Region / Zone** | us-central1 (Always Free eligible) |
| **Machine Type** | e2-micro (0.25-2 vCPU, 1 shared core, 1GB RAM) |
| **Boot Disk** | Ubuntu 22.04 LTS, 30GB standard persistent disk (pd-standard) |
| **External IP** | `34.45.235.139` |
| **Firewall Rules** | HTTP (80), HTTPS (443), TCP 8000 (custom rule: `allow-8000`) |

### URLs

| Endpoint | URL |
|---|---|
| **Health Check** | https://elasticresearchagent.duckdns.org/api/health |
| **MCP Endpoint** | https://elasticresearchagent.duckdns.org/mcp |
| **Research API** | https://elasticresearchagent.duckdns.org/api/research |
| **Verify API** | https://elasticresearchagent.duckdns.org/api/verify |
| **Slack: Add to Slack** | https://elasticresearchagent.duckdns.org/slack/install |
| **Slack: Events** | https://elasticresearchagent.duckdns.org/slack/events |
| **Direct (no SSL)** | http://34.45.235.139:8000 |

### SSH Access

Via Google Cloud Console: **Compute Engine > VM Instances > SSH button**

Or via gcloud CLI:
```bash
gcloud compute ssh research-agent --zone=us-central1-a
```

---

## HTTPS / SSL (Caddy + DuckDNS)

### DuckDNS

| Field | Value |
|---|---|
| **Domain** | elasticresearchagent.duckdns.org |
| **Points to** | 34.45.235.139 |
| **Service** | [duckdns.org](https://www.duckdns.org) (free) |
| **Expiry** | Domains expire after **30 days without an update**. See maintenance section below. |

### Caddy (Reverse Proxy)

Caddy runs as a systemd service and automatically provisions + renews Let's Encrypt SSL certificates.

**Config file:** `/etc/caddy/Caddyfile`
```
elasticresearchagent.duckdns.org {
    reverse_proxy localhost:8000
}
```

**Manage Caddy:**
```bash
# Check status
sudo systemctl status caddy

# Restart (e.g. after config change)
sudo systemctl restart caddy

# View logs
sudo journalctl -u caddy --no-pager -n 50
```

**SSL certificate renewal:** Caddy handles this automatically. No manual action needed — it renews certificates before they expire.

### DuckDNS Maintenance (IMPORTANT)

DuckDNS domains expire if not updated for 30 days. Set up a cron job on the VM to keep it alive:

```bash
# Get your DuckDNS token from https://www.duckdns.org
# Replace YOUR_TOKEN below

(crontab -l 2>/dev/null; echo "*/5 * * * * curl -s 'https://www.duckdns.org/update?domains=elasticresearchagent&token=YOUR_TOKEN&ip=' > /dev/null 2>&1") | crontab -
```

This pings DuckDNS every 5 minutes to keep the domain active and update the IP if it ever changes.

---

## Server Setup (on the VM)

### Directory Structure
```
~/Research_Agent/
├── server/
│   ├── main.py          # FastAPI entry point (includes Slack routes)
│   ├── mcp_server.py    # MCP server (research_literature_review + research_draft tools)
│   ├── config.py        # Loads .env, agent IDs, headers
│   └── services/
│       ├── agent.py     # Elastic Agent Builder streaming client
│       └── orchestrator.py  # Research-review loop orchestrator
├── slack_bot/
│   ├── bolt_app.py      # Slack Bolt app with OAuth (multi-workspace)
│   ├── handlers.py      # /research slash command handler
│   └── formatting.py    # Markdown → Slack mrkdwn conversion
├── data/                # Slack OAuth installation tokens (not in git)
├── venv/                # Python virtual environment
├── .env                 # API keys (not in git)
├── reports/             # Auto-saved markdown reports
└── server.log           # uvicorn output log
```

### Environment Variables (.env)

```env
ELASTIC_API_KEY=your-elastic-api-key
KIBANA_URL=https://my-elasticsearch-project-a97d4e.kb.us-central1.gcp.elastic.cloud
ALLOWED_ORIGINS=https://elasticresearchagent.netlify.app

# Slack Bot (OAuth / HTTP mode)
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret
SLACK_SIGNING_SECRET=your-signing-secret
```

The Slack variables are optional — if not set, the Slack routes are not mounted and the rest of the server works normally.

### Python Dependencies (installed in venv)

```bash
pip install fastapi uvicorn[standard] httpx python-dotenv elasticsearch mcp[cli] fpdf2 slack-bolt aiohttp
```

Note: PyTorch/sentence-transformers are NOT needed on the server. The MCP server only makes HTTP calls to Elastic Agent Builder — no local ML inference.

### Starting the Server

The server runs as a systemd service (`research-agent.service`) which auto-starts on boot and auto-restarts on failure.

**Manage the service:**
```bash
# Start / stop / restart
sudo systemctl start research-agent
sudo systemctl stop research-agent
sudo systemctl restart research-agent

# Check status
sudo systemctl status research-agent

# View logs (live tail)
sudo journalctl -u research-agent -f

# View last 50 log lines
sudo journalctl -u research-agent -n 50 --no-pager
```

**If port 8000 is stuck** (e.g., after a crash or stale process):
```bash
sudo fuser -k 8000/tcp 2>/dev/null; sudo systemctl restart research-agent
```

**Foreground (for debugging only):**
```bash
sudo systemctl stop research-agent
cd ~/Research_Agent
source venv/bin/activate
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

---

## Claude Desktop MCP Configuration

Remote MCP servers must be added through the Claude Desktop UI, not the config file.

**Steps:**
1. Open Claude Desktop
2. Go to **Settings > Connectors**
3. Add a new connector with the URL: `https://elasticresearchagent.duckdns.org/mcp`

The research tools will appear automatically after adding the connector. No API keys or local setup required — the GCP server handles everything.

**Requirements:** Claude Desktop (Pro, Max, Team, or Enterprise plan).

### Available MCP Tools

| Tool | Description | Duration |
|---|---|---|
| `research_literature_review` | Full multi-agent pipeline with peer review | 5-8 min |
| `research_draft` | Research agent only, no peer review (faster) | 2-3 min |
| `verify_claim` | Verify a claim against the research corpus | 2-3 min |

---

## Slack Bot

The Slack bot runs inside the FastAPI server (no separate process). It uses OAuth for multi-workspace distribution — anyone can install it via the "Add to Slack" link.

| Field | Value |
|---|---|
| **Add to Slack** | https://elasticresearchagent.duckdns.org/slack/install |
| **OAuth Redirect** | https://elasticresearchagent.duckdns.org/slack/oauth_redirect |
| **Events Endpoint** | https://elasticresearchagent.duckdns.org/slack/events |
| **Slash Commands** | `/research <topic>`, `/check-claim <claim>` |
| **Token Storage** | `data/installations/` (per-workspace, on disk) |
| **Cost** | $0 (Slack free tier) |

The Slack routes are conditional — only mounted when `SLACK_CLIENT_ID` and `SLACK_SIGNING_SECRET` are set in `.env`. See `SLACK.md` for full setup and troubleshooting.

---

## Frontend (Netlify)

| Field | Value |
|---|---|
| **URL** | https://elasticresearchagent.netlify.app |
| **Platform** | Netlify (free tier) |
| **Framework** | React + Vite + Tailwind |
| **Build command** | `npm install && npm run build` |
| **Publish directory** | `frontend/dist` |
| **Base directory** | `frontend` |
| **Config file** | `netlify.toml` (in repo root) |

### Environment Variables (Netlify)

| Key | Value |
|---|---|
| `VITE_API_URL` | `https://elasticresearchagent.duckdns.org/api/research` |

### Auto-Deploy

Netlify auto-deploys on every push to master. No manual action needed.

---

## Costs

| Resource | Cost | Notes |
|---|---|---|
| GCP e2-micro compute | **$0/month** | Free forever (Always Free tier) |
| GCP 30GB standard disk | **$0/month** | Must be `pd-standard` type |
| GCP External IP | **~$3.65/month** | Since Feb 2024 GCP charges for external IPv4 |
| GCP Network egress | **$0** (first 1GB/month) | ~$0.12/GB after that |
| DuckDNS domain | **$0** | Free, must be refreshed every 30 days (cron job handles this) |
| Caddy / Let's Encrypt SSL | **$0** | Auto-renewing, free certificates |
| Netlify hosting | **$0** | Free tier (100GB bandwidth/month) |
| Slack bot (OAuth/HTTP) | **$0** | Free tier, runs inside existing server |
| Elastic Cloud | **Per your plan** | Depends on your Elastic subscription |
| **Total (excl. Elastic)** | **~$0-4/month** | Mostly the external IP charge |

### Cost Monitoring

Set up a billing alert: **Billing > Budgets & Alerts > Create Budget** with a $1 threshold to get notified of any charges.

---

## Elastic Cloud Details

| Field | Value |
|---|---|
| **Kibana URL** | https://my-elasticsearch-project-a97d4e.kb.us-central1.gcp.elastic.cloud |
| **Elasticsearch Endpoint** | https://my-elasticsearch-project-a97d4e.es.us-central1.gcp.elastic.cloud:443 |
| **API Key** | (stored in `.env` on the VM — not committed to repo) |
| **Research Agent ID** | research_literature_review_agent |
| **Reviewer Agent ID** | peer_review_agent |
| **Claim Verification Agent ID** | claim_verification_agent |
| **Max Iterations** | 2 (literature review only) |
| **Agent Timeout** | 600 seconds |

---

## GitHub Repository

| Field | Value |
|---|---|
| **Repo** | https://github.com/Aaryan126/Research_Agent |
| **Branch** | master |
| **Visibility** | Private |

### Updating the Server

To pull new changes on the VM:
```bash
cd ~/Research_Agent
git pull origin master
sudo fuser -k 8000/tcp 2>/dev/null; sudo systemctl restart research-agent
```

Verify it's running:
```bash
sudo systemctl status research-agent
```

---

## Firewall Rules

| Rule Name | Direction | Action | Source | Protocol/Port |
|---|---|---|---|---|
| default-allow-http | Ingress | Allow | 0.0.0.0/0 | TCP 80 |
| default-allow-https | Ingress | Allow | 0.0.0.0/0 | TCP 443 |
| allow-8000 | Ingress | Allow | 0.0.0.0/0 | TCP 8000 |

---

## Potential Concerns & Maintenance

### DuckDNS Domain Expiry
DuckDNS domains expire after **30 days** without an update. Set up the cron job described in the HTTPS section above to prevent this. If the domain expires, you just log back into duckdns.org and re-create it.

### GCP VM IP Change
The external IP is **ephemeral** (not static). It can change if the VM is stopped and restarted (rare for Always Free VMs, but possible during GCP maintenance). If this happens:
1. Update the IP on DuckDNS
2. The cron job (if set up) will auto-update DuckDNS with the new IP

To avoid this, you can reserve a static IP in GCP (but this adds ~$3.65/month).

### SSL Certificate Renewal
Caddy automatically renews Let's Encrypt certificates before they expire (every 90 days). No action needed.

### VM Reboot
The systemd service (`research-agent.service`) is already enabled and will auto-restart uvicorn on VM reboot. No manual action needed.

The service file is at `/etc/systemd/system/research-agent.service`. If you need to recreate it:
```bash
sudo tee /etc/systemd/system/research-agent.service > /dev/null <<EOF
[Unit]
Description=Research Agent FastAPI Server
After=network.target

[Service]
User=aaryan_kandiah
WorkingDirectory=/home/aaryan_kandiah/Research_Agent
ExecStart=/home/aaryan_kandiah/Research_Agent/venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
EnvironmentFile=/home/aaryan_kandiah/Research_Agent/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable research-agent
sudo systemctl start research-agent
```

### Elastic Cloud API Key
The API key does not expire by default, but it can be revoked from the Elastic Cloud console. If the key is rotated, update `.env` on the VM and restart the server.

### Netlify Build Failures
If a push to master breaks the build, Netlify keeps the last successful deploy live. Check **Deploys** in the Netlify dashboard for error logs.

---

## Troubleshooting

### Server not responding
```bash
# Check systemd service status
sudo systemctl status research-agent

# Check server logs
sudo journalctl -u research-agent -n 50 --no-pager

# Check Caddy logs
sudo journalctl -u caddy --no-pager -n 20

# Restart everything
sudo fuser -k 8000/tcp 2>/dev/null; sudo systemctl restart research-agent
sudo systemctl restart caddy
```

### SSL certificate issues
```bash
# Check Caddy status and cert info
sudo systemctl status caddy
sudo journalctl -u caddy --no-pager -n 50

# Force restart (re-provisions cert if needed)
sudo systemctl restart caddy
```

### DuckDNS domain not resolving
1. Go to https://www.duckdns.org and verify the domain exists and IP is correct
2. If expired, re-create the domain and update the IP
3. Set up the cron job to prevent future expiry

### Cannot clone repo on VM
The repo is private. Use a GitHub Personal Access Token:
1. GitHub > Settings > Developer settings > Personal access tokens > Tokens (classic)
2. Generate token with `repo` scope
3. Use token as password when cloning
