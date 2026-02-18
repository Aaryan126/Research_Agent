"""Elastic Agent Builder converse streaming client."""

import json
import logging
from typing import AsyncGenerator

import httpx

from server.config import KIBANA_URL, HEADERS, AGENT_TIMEOUT

logger = logging.getLogger(__name__)


async def stream_converse(
    agent_id: str,
    message: str,
    conversation_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream a conversation with an Elastic Agent Builder agent.

    Calls POST {KIBANA_URL}/api/agent_builder/converse/async and yields
    parsed SSE events as dicts: {"event": "<type>", "data": {<payload>}}.

    Never raises — yields an error event on failure instead.
    """
    url = f"{KIBANA_URL}/api/agent_builder/converse/async"
    payload: dict = {
        "input": message,
        "agent_id": agent_id,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    # Use same headers but request SSE response
    headers = {**HEADERS, "Accept": "text/event-stream"}

    logger.info(
        "Calling converse API: agent_id=%s url=%s payload_keys=%s",
        agent_id, url, list(payload.keys()),
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(AGENT_TIMEOUT, connect=30),
            follow_redirects=True,
        ) as client:
            async with client.stream(
                "POST", url, json=payload, headers=headers,
            ) as response:
                logger.info("Converse API response status: %s", response.status_code)

                if response.status_code != 200:
                    body = await response.aread()
                    detail = body.decode(errors="replace")
                    logger.error(
                        "Converse API error %s for agent %s: %s",
                        response.status_code, agent_id, detail,
                    )
                    yield {
                        "event": "error",
                        "data": {
                            "message": f"Agent API returned {response.status_code}: {detail[:500]}",
                        },
                    }
                    return

                current_event = ""
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                    elif line.startswith("data: ") and current_event:
                        raw = line[6:]
                        data = _parse_data(raw)
                        # Elastic API wraps event payloads in a "data" key
                        inner = data.get("data")
                        if isinstance(inner, dict):
                            data = inner
                        yield {"event": current_event, "data": data}
                        current_event = ""
                    elif line.strip() == "":
                        current_event = ""

    except GeneratorExit:
        logger.debug("stream_converse generator closed for agent %s", agent_id)
        return
    except BaseException as exc:
        logger.exception("stream_converse failed for agent %s", agent_id)
        yield {
            "event": "error",
            "data": {"message": f"Agent connection error: {type(exc).__name__}: {exc}"},
        }


def _parse_data(raw: str) -> dict:
    """Parse SSE data field, handling malformed JSON gracefully."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"raw": raw}
