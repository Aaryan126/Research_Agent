"""SSE streaming endpoint for research with real-time reasoning traces."""

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.services.orchestrator import run_research_loop, run_claim_verification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class ResearchRequest(BaseModel):
    topic: str
    mode: str = "research"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _safe_stream(topic: str, mode: str = "research"):
    """Wrapper that guarantees the SSE stream always ends cleanly.

    Catches any exception from the orchestrator and converts it to
    error + done events so the chunked encoding is properly terminated.
    """
    done_sent = False
    try:
        generator = (
            run_claim_verification(topic) if mode == "verify"
            else run_research_loop(topic)
        )
        async for chunk in generator:
            yield chunk
            if "event: done" in chunk:
                done_sent = True
    except GeneratorExit:
        # Client disconnected — clean shutdown, nothing to send
        logger.info("Client disconnected during research stream")
        return
    except BaseException as exc:
        logger.exception("Research stream failed with %s", type(exc).__name__)
        yield _sse("error", {"message": f"Internal error: {type(exc).__name__}: {exc}"})
        yield _sse("done", {})
        done_sent = True
    finally:
        if not done_sent:
            logger.warning("Stream ended without done event — sending done")
            try:
                yield _sse("done", {})
            except GeneratorExit:
                pass


@router.post("/research")
async def research(req: ResearchRequest):
    """Start a research or verification workflow and stream reasoning traces via SSE."""
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic must not be empty")
    if req.mode not in ("research", "verify"):
        raise HTTPException(status_code=400, detail="Mode must be 'research' or 'verify'")

    return StreamingResponse(
        _safe_stream(req.topic.strip(), req.mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class VerifyRequest(BaseModel):
    claim: str


@router.post("/verify")
async def verify(req: VerifyRequest):
    """Start a claim verification workflow. Alias for /research with mode=verify."""
    if not req.claim.strip():
        raise HTTPException(status_code=400, detail="Claim must not be empty")

    return StreamingResponse(
        _safe_stream(req.claim.strip(), "verify"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/test-sse")
async def test_sse():
    """Diagnostic endpoint to verify SSE streaming works."""
    async def _generate():
        yield _sse("agent_start", {"agent": "Test Agent", "agent_id": "test", "iteration": 1})
        yield _sse("reasoning", {"text": "This is a test reasoning event.", "agent": "Test Agent", "iteration": 1})
        yield _sse("agent_end", {"agent": "Test Agent", "iteration": 1})
        yield _sse("result", {
            "report": "# Test Report\n\nSSE streaming is working correctly.",
            "review": None,
            "iteration_info": "Test (no Elastic API call)",
            "iterations": ["Test: PASS"],
        })
        yield _sse("done", {})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
