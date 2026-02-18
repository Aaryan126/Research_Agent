"""Custom MCP server exposing the research literature review orchestration loop."""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime

# Ensure project root is on sys.path so `server.*` imports work
# regardless of the working directory the process is launched from.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.chdir(_project_root)

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Research Literature Review Agent",
    instructions=(
        "Provides academic literature review and claim verification tools powered by "
        "Elastic Agent Builder. Three tools are available:\n"
        "- research_literature_review: Full multi-agent pipeline with peer review (5-8 min)\n"
        "- research_draft: Research agent only, no peer review (2-3 min, faster)\n"
        "- verify_claim: Verify a claim against scientific literature (2-3 min)\n\n"
        "IMPORTANT: Always display the COMPLETE tool output to the user exactly as returned. "
        "Do NOT summarize, truncate, or condense the output. The user expects "
        "the full report with all sections, citations, and references.\n\n"
        "After displaying the full report, always generate a downloadable PDF of the "
        "complete output and provide it to the user."
    ),
    transport_security=TransportSecuritySettings(
        allowed_hosts=["elasticresearchagent.duckdns.org", "localhost", "127.0.0.1"],
    ),
)


@mcp.tool()
async def research_literature_review(topic: str, ctx: Context) -> str:
    """Run a full peer-reviewed literature review on a research topic.

    Orchestrates a multi-agent loop:
    1. Research Agent searches papers, analyzes evidence, writes a draft
    2. Peer Review Agent evaluates the draft for accuracy and completeness
    3. If revision needed, Research Agent revises based on feedback
    4. Up to 2 iterations until the review passes

    This tool takes several minutes to complete. Progress updates are provided
    throughout.

    Args:
        topic: The research topic to investigate
              (e.g., "hallucination in multi-agent systems")
    """
    from server.services.orchestrator import run_research_loop

    report = None
    iteration_info = None
    step = 0

    try:
        async for sse_line in run_research_loop(topic):
            if not sse_line.startswith("event: "):
                continue

            lines = sse_line.strip().split("\n")
            event_type = lines[0].replace("event: ", "")
            data_str = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if event_type == "agent_start":
                agent = data.get("agent", "Agent")
                iteration = data.get("iteration", 1)
                await ctx.info(f"{agent} starting (iteration {iteration})...")
                step += 1
                await ctx.report_progress(step, 10)

            elif event_type == "reasoning":
                text = data.get("text", "")
                if text:
                    await ctx.info(f"Thinking: {text[:150]}")

            elif event_type == "tool_call":
                tool_id = data.get("tool_id", "")
                await ctx.info(f"Using tool: {tool_id}")

            elif event_type == "agent_end":
                agent = data.get("agent", "Agent")
                await ctx.info(f"{agent} finished.")
                step += 1
                await ctx.report_progress(step, 10)

            elif event_type == "verdict":
                verdict = data.get("verdict", "")
                iteration = data.get("iteration", 1)
                await ctx.info(
                    f"Peer review verdict (iteration {iteration}): {verdict}"
                )

            elif event_type == "result":
                report = data.get("report")
                iteration_info = data.get("iteration_info")

            elif event_type == "error":
                msg = data.get("message", "Unknown error")
                return f"Error: {msg}"

    except (asyncio.CancelledError, Exception) as e:
        if report:
            logger.warning(f"Request interrupted ({type(e).__name__}), returning partial report.")
            return _wrap_output(report, topic, "Note: Peer review may not have completed due to timeout.")
        logger.error(f"Request failed before report was generated: {e}")
        raise

    if not report:
        return "Error: No report was generated."

    return _wrap_output(report, topic, iteration_info)


@mcp.tool()
async def research_draft(topic: str, ctx: Context) -> str:
    """Run a literature review on a research topic (research agent only, no peer review).

    This is a faster alternative to research_literature_review that skips the
    peer review step. The Research Agent searches papers, analyzes evidence,
    and writes a literature review draft. Typically completes in 2-3 minutes.

    Use this when you want quick results without the review cycle.

    Args:
        topic: The research topic to investigate
              (e.g., "hallucination in multi-agent systems")
    """
    from server.services.orchestrator import run_research_loop

    report = None
    iteration_info = None
    step = 0

    try:
        async for sse_line in run_research_loop(topic, skip_review=True):
            if not sse_line.startswith("event: "):
                continue

            lines = sse_line.strip().split("\n")
            event_type = lines[0].replace("event: ", "")
            data_str = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if event_type == "agent_start":
                agent = data.get("agent", "Agent")
                await ctx.info(f"{agent} starting...")
                step += 1
                await ctx.report_progress(step, 5)

            elif event_type == "reasoning":
                text = data.get("text", "")
                if text:
                    await ctx.info(f"Thinking: {text[:150]}")

            elif event_type == "tool_call":
                tool_id = data.get("tool_id", "")
                await ctx.info(f"Using tool: {tool_id}")

            elif event_type == "agent_end":
                agent = data.get("agent", "Agent")
                await ctx.info(f"{agent} finished.")
                step += 1
                await ctx.report_progress(step, 5)

            elif event_type == "result":
                report = data.get("report")
                iteration_info = data.get("iteration_info")

            elif event_type == "error":
                msg = data.get("message", "Unknown error")
                return f"Error: {msg}"

    except (asyncio.CancelledError, Exception) as e:
        if report:
            logger.warning(f"Request interrupted ({type(e).__name__}), returning partial report.")
            return _wrap_output(report, topic)
        logger.error(f"Request failed before report was generated: {e}")
        raise

    if not report:
        return "Error: No report was generated."

    return _wrap_output(report, topic, iteration_info)


@mcp.tool()
async def verify_claim(claim: str, ctx: Context) -> str:
    """Verify a factual claim against scientific literature.

    Uses the Claim Verification Agent to evaluate whether a claim is
    supported, contradicted, or inconclusive based on available evidence
    in the corpus. Single-pass agent — no peer review loop.
    Typically completes in 2-3 minutes.

    Args:
        claim: The factual claim to verify
              (e.g., "Multi-agent systems outperform single-agent approaches")
    """
    from server.services.orchestrator import run_claim_verification

    report = None
    iteration_info = None
    step = 0

    try:
        async for sse_line in run_claim_verification(claim):
            if not sse_line.startswith("event: "):
                continue

            lines = sse_line.strip().split("\n")
            event_type = lines[0].replace("event: ", "")
            data_str = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if event_type == "agent_start":
                agent = data.get("agent", "Agent")
                await ctx.info(f"{agent} starting...")
                step += 1
                await ctx.report_progress(step, 5)

            elif event_type == "reasoning":
                text = data.get("text", "")
                if text:
                    await ctx.info(f"Thinking: {text[:150]}")

            elif event_type == "tool_call":
                tool_id = data.get("tool_id", "")
                await ctx.info(f"Using tool: {tool_id}")

            elif event_type == "agent_end":
                agent = data.get("agent", "Agent")
                await ctx.info(f"{agent} finished.")
                step += 1
                await ctx.report_progress(step, 5)

            elif event_type == "result":
                report = data.get("report")
                iteration_info = data.get("iteration_info")

            elif event_type == "error":
                msg = data.get("message", "Unknown error")
                return f"Error: {msg}"

    except (asyncio.CancelledError, Exception) as e:
        if report:
            logger.warning(f"Request interrupted ({type(e).__name__}), returning partial report.")
            return _wrap_output(report, claim)
        logger.error(f"Request failed before report was generated: {e}")
        raise

    if not report:
        return "Error: No verification report was generated."

    return _wrap_output(report, claim, iteration_info)


_REPORTS_DIR = os.path.join(_project_root, "reports")
os.makedirs(_REPORTS_DIR, exist_ok=True)


def _slugify(text: str) -> str:
    """Convert a topic string to a filename-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "_", slug).strip("_")
    return slug[:60]


def _save_report(report: str, topic: str) -> str:
    """Save the report as a markdown file. Returns the file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify(topic)
    md_path = os.path.join(_REPORTS_DIR, f"{slug}_{timestamp}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    return md_path


def _wrap_output(report: str, topic: str, iteration_info: str | None = None) -> str:
    """Save report to file and return report text + file path."""
    md_path = _save_report(report, topic)

    output = f"Full report saved to: {md_path}\n\n"
    output += report
    if iteration_info:
        output += f"\n\n---\n*{iteration_info}*"
    return output


if __name__ == "__main__":
    mcp.run(transport="stdio")
