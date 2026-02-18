"""Tests for the MCP server — no running server or network required.

Run with:  py -m pytest tests/test_mcp_server.py -v
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from server.mcp_server import mcp, research_literature_review


# ---------------------------------------------------------------------------
# 1. Schema / registration tests
# ---------------------------------------------------------------------------

class TestToolRegistration:
    """Verify the MCP tool is registered with correct metadata."""

    def _get_tool(self):
        tools = mcp._tool_manager.list_tools()
        by_name = {t.name: t for t in tools}
        return by_name.get("research_literature_review")

    def test_tool_is_registered(self):
        tool = self._get_tool()
        assert tool is not None, "research_literature_review tool not found"

    def test_tool_has_description(self):
        tool = self._get_tool()
        assert "peer-reviewed" in tool.description.lower()
        assert "literature review" in tool.description.lower()

    def test_tool_has_topic_parameter(self):
        tool = self._get_tool()
        schema = tool.parameters
        assert "topic" in schema.get("properties", {}), "Missing 'topic' parameter"
        assert "topic" in schema.get("required", []), "'topic' should be required"

    def test_topic_parameter_is_string(self):
        tool = self._get_tool()
        topic_schema = tool.parameters["properties"]["topic"]
        assert topic_schema.get("type") == "string"

    def test_server_name(self):
        assert mcp.name == "Research Literature Review Agent"

    def test_server_has_instructions(self):
        assert mcp.instructions is not None
        assert "Elastic Agent Builder" in mcp.instructions


# ---------------------------------------------------------------------------
# 2. SSE parsing / integration tests (mock orchestrator)
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict) -> str:
    """Build an SSE string identical to what the real orchestrator yields."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Simulates a successful single-iteration run
MOCK_SSE_SUCCESS = [
    _sse("agent_start", {"agent": "Research Agent", "iteration": 1}),
    _sse("reasoning", {"text": "Searching for papers on the topic..."}),
    _sse("tool_call", {"tool_id": "search_papers"}),
    _sse("tool_result", {"tool_id": "search_papers", "result": "5 papers found"}),
    _sse("message_chunk", {"text": "# Literature Review\n..."}),
    _sse("agent_end", {"agent": "Research Agent", "iteration": 1}),
    _sse("agent_start", {"agent": "Peer Review Agent", "iteration": 1}),
    _sse("reasoning", {"text": "Evaluating the draft..."}),
    _sse("agent_end", {"agent": "Peer Review Agent", "iteration": 1}),
    _sse("verdict", {"verdict": "PASS", "iteration": 1}),
    _sse("result", {
        "report": "# Literature Review\n\nThis is the final report.",
        "review": "All criteria met.",
        "iteration_info": "Iteration 1 (verdict: PASS)",
    }),
    _sse("done", {}),
]

# Simulates an error mid-run
MOCK_SSE_ERROR = [
    _sse("agent_start", {"agent": "Research Agent", "iteration": 1}),
    _sse("error", {"message": "Agent timed out after 600s"}),
]

# Simulates an empty run (no result event)
MOCK_SSE_EMPTY = [
    _sse("agent_start", {"agent": "Research Agent", "iteration": 1}),
    _sse("agent_end", {"agent": "Research Agent", "iteration": 1}),
    _sse("done", {}),
]

# Simulates a multi-iteration run (revision needed then pass)
MOCK_SSE_TWO_ITERATIONS = [
    _sse("agent_start", {"agent": "Research Agent", "iteration": 1}),
    _sse("agent_end", {"agent": "Research Agent", "iteration": 1}),
    _sse("agent_start", {"agent": "Peer Review Agent", "iteration": 1}),
    _sse("agent_end", {"agent": "Peer Review Agent", "iteration": 1}),
    _sse("verdict", {"verdict": "REVISION_NEEDED", "iteration": 1}),
    _sse("agent_start", {"agent": "Research Agent", "iteration": 2}),
    _sse("agent_end", {"agent": "Research Agent", "iteration": 2}),
    _sse("agent_start", {"agent": "Peer Review Agent", "iteration": 2}),
    _sse("agent_end", {"agent": "Peer Review Agent", "iteration": 2}),
    _sse("verdict", {"verdict": "PASS", "iteration": 2}),
    _sse("result", {
        "report": "# Revised Report\n\nImproved content.",
        "review": "Looks good now.",
        "iteration_info": "Iteration 2 (verdict: PASS)",
    }),
    _sse("done", {}),
]


async def _mock_generator(sse_events):
    """Async generator that yields pre-built SSE strings."""
    for event in sse_events:
        yield event


def _make_mock_ctx():
    """Create a mock Context with async methods."""
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.debug = AsyncMock()
    ctx.report_progress = AsyncMock()
    return ctx


class TestSSEParsing:
    """Test the tool function's SSE parsing with mocked orchestrator."""

    @pytest.mark.asyncio
    async def test_successful_run_returns_report(self):
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(MOCK_SSE_SUCCESS),
        ):
            result = await research_literature_review(topic="test topic", ctx=ctx)

        assert "# Literature Review" in result
        assert "This is the final report." in result
        assert "Iteration 1 (verdict: PASS)" in result

    @pytest.mark.asyncio
    async def test_successful_run_reports_progress(self):
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(MOCK_SSE_SUCCESS),
        ):
            await research_literature_review(topic="test topic", ctx=ctx)

        # Should have called ctx.info for agent_start, reasoning, tool_call, agent_end, verdict
        info_messages = [call.args[0] for call in ctx.info.call_args_list]
        assert any("Research Agent starting" in m for m in info_messages)
        assert any("Peer Review Agent" in m for m in info_messages)
        assert any("PASS" in m for m in info_messages)

        # Should have reported progress
        assert ctx.report_progress.call_count > 0

    @pytest.mark.asyncio
    async def test_error_event_returns_error_string(self):
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(MOCK_SSE_ERROR),
        ):
            result = await research_literature_review(topic="test topic", ctx=ctx)

        assert result.startswith("Error:")
        assert "timed out" in result

    @pytest.mark.asyncio
    async def test_empty_run_returns_no_report_error(self):
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(MOCK_SSE_EMPTY),
        ):
            result = await research_literature_review(topic="test topic", ctx=ctx)

        assert result == "Error: No report was generated."

    @pytest.mark.asyncio
    async def test_two_iteration_run(self):
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(MOCK_SSE_TWO_ITERATIONS),
        ):
            result = await research_literature_review(topic="test topic", ctx=ctx)

        assert "# Revised Report" in result
        assert "Iteration 2 (verdict: PASS)" in result

        # Should have reported both REVISION_NEEDED and PASS verdicts
        info_messages = [call.args[0] for call in ctx.info.call_args_list]
        assert any("REVISION_NEEDED" in m for m in info_messages)
        assert any("PASS" in m for m in info_messages)

    @pytest.mark.asyncio
    async def test_tool_call_logged(self):
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(MOCK_SSE_SUCCESS),
        ):
            await research_literature_review(topic="test topic", ctx=ctx)

        info_messages = [call.args[0] for call in ctx.info.call_args_list]
        assert any("search_papers" in m for m in info_messages)

    @pytest.mark.asyncio
    async def test_reasoning_truncated_to_150_chars(self):
        long_reasoning = "A" * 300
        events = [
            _sse("reasoning", {"text": long_reasoning}),
            _sse("result", {"report": "done", "iteration_info": None}),
            _sse("done", {}),
        ]
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(events),
        ):
            await research_literature_review(topic="test", ctx=ctx)

        info_messages = [call.args[0] for call in ctx.info.call_args_list]
        reasoning_msgs = [m for m in info_messages if m.startswith("Thinking:")]
        assert len(reasoning_msgs) == 1
        # "Thinking: " is 10 chars + 150 chars of content = 160 max
        assert len(reasoning_msgs[0]) <= 160

    @pytest.mark.asyncio
    async def test_malformed_json_skipped_gracefully(self):
        events = [
            "event: agent_start\ndata: {not valid json}\n\n",
            _sse("result", {"report": "Final report", "iteration_info": None}),
            _sse("done", {}),
        ]
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(events),
        ):
            result = await research_literature_review(topic="test", ctx=ctx)

        assert "Final report" in result

    @pytest.mark.asyncio
    async def test_non_sse_lines_skipped(self):
        events = [
            "some random line",
            ": comment line",
            _sse("result", {"report": "Report content", "iteration_info": None}),
            _sse("done", {}),
        ]
        ctx = _make_mock_ctx()
        with patch(
            "server.services.orchestrator.run_research_loop",
            return_value=_mock_generator(events),
        ):
            result = await research_literature_review(topic="test", ctx=ctx)

        assert "Report content" in result


# ---------------------------------------------------------------------------
# 3. FastAPI mount test
# ---------------------------------------------------------------------------

class TestFastAPIMount:
    """Verify the MCP endpoint is mounted on the FastAPI app."""

    def test_mcp_route_exists(self):
        from server.main import app
        route_paths = [r.path for r in app.routes]
        assert "/mcp" in route_paths, f"'/mcp' not in routes: {route_paths}"

    def test_existing_routes_preserved(self):
        from server.main import app
        route_paths = [r.path for r in app.routes]
        assert "/api/health" in route_paths
        assert "/api/research" in route_paths
