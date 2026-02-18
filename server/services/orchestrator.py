"""Research-review loop orchestrator using Elastic Converse streaming."""

import json
import logging
import re
from typing import AsyncGenerator

from server.config import RESEARCHER_AGENT_ID, REVIEWER_AGENT_ID, CLAIM_VERIFICATION_AGENT_ID, MAX_ITERATIONS
from server.services.agent import stream_converse

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _build_researcher_prompt(topic: str, iteration: int,
                             prior_draft: str | None,
                             review_feedback: str | None) -> str:
    """Build the researcher agent prompt for the given iteration."""
    if iteration == 1:
        return topic

    revision_intro = (
        "You previously produced the following literature review:\n\n"
        f"{prior_draft}\n\n"
        "A peer reviewer evaluated this report and identified the following issues:\n\n"
        f"{review_feedback}\n\n"
    )

    if iteration == MAX_ITERATIONS:
        return (
            f"{revision_intro}"
            "This is the final revision opportunity. Please carefully address all "
            "remaining CRITICAL and MAJOR issues. Produce a complete revised report "
            "in the same 6-section format. Use your search tools to find correct "
            "evidence for any citation issues."
        )

    return (
        f"{revision_intro}"
        "Please revise the report to address all CRITICAL and MAJOR issues identified "
        "in the review. Produce a complete revised report in the same 6-section format. "
        "Use your search tools to find correct evidence for any citation issues."
    )


def _extract_paper_ids(report: str) -> list[str]:
    """Extract paper_ids from the References section of a researcher report."""
    paper_ids: list[str] = []
    refs_match = re.search(r"(?i)#+\s*references?\b", report)
    if not refs_match:
        return paper_ids
    refs_section = report[refs_match.start():]
    for m in re.finditer(r"paper_id:\s*([^\s,)\]]+)", refs_section):
        pid = m.group(1).strip().rstrip(".")
        if pid and pid not in paper_ids:
            paper_ids.append(pid)
    return paper_ids


def _build_reviewer_prompt(draft: str, iteration: int,
                           paper_ids: list[str] | None = None) -> str:
    """Build the reviewer agent prompt."""
    prefix = {
        1: "Review the following literature review report:",
        2: "Review the following revised literature review report:",
    }.get(iteration, "Review the following final revised literature review report:")

    parts = [prefix]

    if paper_ids:
        ids_list = ", ".join(f'"{pid}"' for pid in paper_ids)
        parts.append(
            f"\nCITED PAPER IDS (extracted from References section):\n{ids_list}\n"
            "Use these paper_ids directly for your Step 2 batch verification query "
            "and Step 5 coverage gap analysis. Do not re-discover them through search."
        )

    parts.append(f"\n{draft}")
    return "\n".join(parts)


def _parse_verdict(review_text: str) -> str:
    """Extract PASS or REVISION_NEEDED from reviewer output.

    Falls back to REVISION_NEEDED if not found (conservative).
    """
    match = re.search(r"VERDICT:\s*(PASS|REVISION_NEEDED)", review_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    if "PASS" in review_text.upper().split("VERDICT")[-1] if "VERDICT" in review_text.upper() else False:
        return "PASS"
    return "REVISION_NEEDED"


async def _stream_agent(
    agent_id: str,
    agent_label: str,
    prompt: str,
    iteration: int,
) -> AsyncGenerator[tuple[str, str | None], None]:
    """Stream an agent call, yielding (sse_string, final_message_or_none) tuples.

    Forwards reasoning/tool_call/tool_result/message_chunk events to the client
    and accumulates the agent's final message text from message_chunk events.
    """
    yield _sse("agent_start", {
        "agent": agent_label,
        "agent_id": agent_id,
        "iteration": iteration,
    }), None

    final_message_parts: list[str] = []

    try:
        async for event in stream_converse(agent_id, prompt):
            etype = event["event"]
            edata = event["data"]

            if etype == "error":
                yield _sse("error", {
                    "message": edata.get("message", "Agent error"),
                    "agent": agent_label,
                    "iteration": iteration,
                }), None

            elif etype == "reasoning":
                payload = {
                    "text": edata.get("reasoning", ""),
                    "agent": agent_label,
                    "iteration": iteration,
                }
                yield _sse("reasoning", payload), None

            elif etype == "tool_call":
                payload = {**edata, "agent": agent_label, "iteration": iteration}
                yield _sse("tool_call", payload), None

            elif etype == "tool_result":
                payload = {**edata, "agent": agent_label, "iteration": iteration}
                yield _sse("tool_result", payload), None

            elif etype == "message_chunk":
                text = edata.get("text_chunk", "")
                payload = {"text": text, "agent": agent_label, "iteration": iteration}
                yield _sse("message_chunk", payload), None
                if text:
                    final_message_parts.append(text)

            elif etype == "tool_progress":
                payload = {**edata, "agent": agent_label, "iteration": iteration}
                yield _sse("tool_progress", payload), None

            elif etype == "message_complete":
                text = edata.get("message_content", "")
                if text:
                    final_message_parts = [text]

            elif etype in (
                "conversation_id_set", "conversation_created",
                "thinking_complete", "round_complete",
            ):
                pass  # Internal lifecycle events — no need to forward

            else:
                logger.debug("Unknown event type from %s: %s", agent_id, etype)

    except GeneratorExit:
        logger.debug("_stream_agent generator closed for %s", agent_label)
        return
    except BaseException as exc:
        logger.exception("_stream_agent failed for %s", agent_label)
        yield _sse("error", {
            "message": f"Agent stream error: {type(exc).__name__}: {exc}",
            "agent": agent_label,
            "iteration": iteration,
        }), None

    final_message = "".join(final_message_parts)

    yield _sse("agent_end", {
        "agent": agent_label,
        "iteration": iteration,
    }), final_message


async def run_research_loop(topic: str, skip_review: bool = False) -> AsyncGenerator[str, None]:
    """Orchestrate the research-review loop, yielding SSE event strings.

    Runs up to MAX_ITERATIONS of researcher → reviewer cycles, forwarding
    all agent reasoning events in real-time.

    If skip_review is True, only the researcher agent runs (no peer review).

    Never raises — any exception is converted to an error+done SSE pair.
    """
    try:
        prior_draft: str | None = None
        review_feedback: str | None = None
        latest_report: str | None = None
        latest_review: str | None = None
        iteration_summary: list[str] = []
        final_iteration = 1

        for iteration in range(1, MAX_ITERATIONS + 1):
            final_iteration = iteration

            # --- Researcher Agent ---
            researcher_prompt = _build_researcher_prompt(
                topic, iteration, prior_draft, review_feedback,
            )

            researcher_output = ""
            async for sse_str, final_msg in _stream_agent(
                RESEARCHER_AGENT_ID, "Research Agent", researcher_prompt, iteration,
            ):
                yield sse_str
                if final_msg is not None:
                    researcher_output = final_msg

            if not researcher_output:
                yield _sse("error", {"message": f"Researcher produced no output (iteration {iteration})"})
                yield _sse("done", {})
                return

            latest_report = researcher_output

            # --- Skip review if requested ---
            if skip_review:
                iteration_summary.append(f"Iteration {iteration}: RESEARCH_ONLY")
                break

            # --- Reviewer Agent ---
            paper_ids = _extract_paper_ids(researcher_output)
            reviewer_prompt = _build_reviewer_prompt(
                researcher_output, iteration, paper_ids,
            )

            reviewer_output = ""
            async for sse_str, final_msg in _stream_agent(
                REVIEWER_AGENT_ID, "Peer Review Agent", reviewer_prompt, iteration,
            ):
                yield sse_str
                if final_msg is not None:
                    reviewer_output = final_msg

            if not reviewer_output:
                yield _sse("error", {"message": f"Reviewer produced no output (iteration {iteration})"})
                yield _sse("done", {})
                return

            latest_review = reviewer_output

            # --- Parse verdict ---
            verdict = _parse_verdict(reviewer_output)
            yield _sse("verdict", {"verdict": verdict, "iteration": iteration})
            iteration_summary.append(f"Iteration {iteration}: {verdict}")

            if verdict == "PASS":
                break

            # Prepare for next iteration
            prior_draft = researcher_output
            review_feedback = reviewer_output

        # --- Emit final result ---
        iteration_info = f"Iteration {final_iteration}"
        if skip_review:
            iteration_info += " (research only, no peer review)"
        elif final_iteration == MAX_ITERATIONS and iteration_summary[-1].endswith("REVISION_NEEDED"):
            iteration_info += " (final revision)"
        elif iteration_summary[-1].endswith("PASS"):
            iteration_info += " (verdict: PASS)"

        yield _sse("result", {
            "report": latest_report,
            "review": latest_review,
            "iteration_info": iteration_info,
            "iterations": iteration_summary,
        })

        yield _sse("done", {})

    except Exception as exc:
        logger.exception("run_research_loop failed")
        yield _sse("error", {"message": f"Internal error: {type(exc).__name__}: {exc}"})
        yield _sse("done", {})


async def run_claim_verification(claim: str) -> AsyncGenerator[str, None]:
    """Run a single-pass claim verification, yielding SSE event strings.

    Uses the Claim Verification Agent to evaluate a claim against the corpus.
    No peer review loop — single pass only.

    Never raises — any exception is converted to an error+done SSE pair.
    """
    try:
        agent_output = ""
        async for sse_str, final_msg in _stream_agent(
            CLAIM_VERIFICATION_AGENT_ID,
            "Claim Verification Agent",
            claim,
            iteration=1,
        ):
            yield sse_str
            if final_msg is not None:
                agent_output = final_msg

        if not agent_output:
            yield _sse("error", {"message": "Claim verification agent produced no output"})
            yield _sse("done", {})
            return

        yield _sse("result", {
            "report": agent_output,
            "review": None,
            "iteration_info": "Claim verification (single pass)",
            "iterations": ["Iteration 1: CLAIM_VERIFICATION"],
        })
        yield _sse("done", {})

    except Exception as exc:
        logger.exception("run_claim_verification failed")
        yield _sse("error", {"message": f"Internal error: {type(exc).__name__}: {exc}"})
        yield _sse("done", {})
