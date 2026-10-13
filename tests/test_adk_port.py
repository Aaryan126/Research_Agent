"""Offline contract tests for the ADK to API adapter and corpus tools."""

import asyncio
import json

from google.adk.events import Event
from google.genai import types

from server.config import RESEARCHER_AGENT_ID
from server.services import agent, corpus_tools
from server.services.orchestrator import run_research_loop


def _event(part: types.Part, partial: bool = False) -> Event:
    return Event(author="researcher", invocation_id="test", partial=partial,
                 content=types.Content(role="model", parts=[part]))


def test_adk_stream_maps_tool_and_final_events(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    events = [
        _event(types.Part(function_call=types.FunctionCall(name="search_papers", args={"query": "agents"}))),
        _event(types.Part(function_response=types.FunctionResponse(
            name="search_papers", response={"passages": [{"paper_id": "p1"}]}))),
        _event(types.Part(text="First "), partial=True),
        _event(types.Part(text="draft"), partial=True),
        _event(types.Part(text="First draft")),
    ]

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        async def run_async(self, **kwargs):
            for event in events:
                yield event

    monkeypatch.setattr(agent, "Runner", FakeRunner)
    result = asyncio.run(_collect(agent.stream_converse(RESEARCHER_AGENT_ID, "topic")))
    assert [item["event"] for item in result] == [
        "tool_call", "tool_result", "message_chunk", "message_chunk", "message_complete",
    ]
    assert result[-1]["data"]["message_content"] == "First draft"


async def _collect(generator):
    return [item async for item in generator]


def test_orchestrator_delivers_adk_report(monkeypatch):
    async def fake_stream(agent_id, message, conversation_id=None):
        yield {"event": "tool_call", "data": {"tool_id": "search_papers", "params": {"query": message}}}
        yield {"event": "message_complete", "data": {"message_content": "# Report"}}

    monkeypatch.setattr("server.services.orchestrator.stream_converse", fake_stream)
    events = asyncio.run(_collect(run_research_loop("topic", skip_review=True)))
    decoded = [(line.split("\n", 1)[0][7:], json.loads(line.split("data: ", 1)[1]))
               for line in events]
    assert ("result", {"report": "# Report", "review": None,
                       "iteration_info": "Iteration 1 (research only, no peer review)",
                       "iterations": ["Iteration 1: RESEARCH_ONLY"]}) in decoded
    assert decoded[-1][0] == "done"


def test_orchestrator_stops_after_adk_error(monkeypatch):
    async def failed_stream(agent_id, message, conversation_id=None):
        yield {"event": "error", "data": {"message": "Vertex AI unavailable"}}

    monkeypatch.setattr("server.services.orchestrator.stream_converse", failed_stream)
    events = asyncio.run(_collect(run_research_loop("topic")))
    assert [event.split("\n", 1)[0] for event in events] == [
        "event: agent_start", "event: error", "event: done",
    ]


def test_corpus_tools_use_existing_indices_and_verify_missing_ids(monkeypatch):
    class FakeES:
        def search(self, **kwargs):
            assert kwargs["index"] == "papers_metadata"
            assert kwargs["query"] == {"terms": {"paper_id": ["p1", "missing"]}}
            return {"hits": {"hits": [{"_score": 1.0, "_source": {
                "paper_id": "p1", "title": "Paper One", "year": 2025,
            }}]}}

    monkeypatch.setattr(corpus_tools, "_client", FakeES)
    result = corpus_tools.get_paper_metadata(["p1", "missing", "p1"])
    assert result["papers"][0]["paper_id"] == "p1"
    assert result["missing_ids"] == ["missing"]
