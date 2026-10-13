"""Google ADK agents using Gemini on Vertex AI and Elasticsearch tools."""

import logging
import os
from typing import AsyncGenerator

from google.adk.agents import Agent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from server.config import (
    CLAIM_VERIFICATION_AGENT_ID, GEMINI_MODEL, RESEARCHER_AGENT_ID, REVIEWER_AGENT_ID,
)
from server.services.corpus_tools import (
    corpus_overview, get_paper_metadata, publication_trends, search_metadata,
    search_papers, top_cited_papers,
)

logger = logging.getLogger(__name__)

RESEARCHER_INSTRUCTION = """You are an academic literature review researcher.
Work only from the indexed Elasticsearch paper corpus and use the supplied tools.
Plan 3-5 subquestions, inspect corpus size and publication trends, find relevant and
influential papers, search full text separately for each subquestion, then search for
counterevidence before writing. Verify titles, authors, years and paper IDs with
get_paper_metadata. Never invent citations or evidence. Say when evidence is thin.

Write only the final report with these sections: Introduction, Research Landscape,
Key Findings, Contradictions and Debates, Research Gaps, Suggested Future Research
Directions, and References. Tag each key finding [SUPPORTED], [CONTESTED], or
[INSUFFICIENT]. Cite papers inline by title, authors and year. Include full title,
all available authors, year and paper_id in numbered References. Distinguish corpus
coverage from general scientific consensus. Do not expose private reasoning.
"""

REVIEWER_INSTRUCTION = """You are an independent peer reviewer of a literature report.
Use get_paper_metadata to verify every cited paper ID, title, author and year. Search
full text to spot-check major claims and alleged contradictions. Search for relevant
highly cited papers omitted from the draft. Check all required sections, confidence
tags, evidence strength, and whether future directions match stated gaps.
Use the corpus tools yourself; do not trust the researcher's citations without checking.

Respond in this exact format:
VERDICT: PASS or REVISION_NEEDED
ISSUES:
- [CRITICAL/MAJOR/MINOR] section: explanation and evidence
MISSED_PAPERS:
- title (paper_id: ID, citations: N) — relevance
SUMMARY:
2-3 sentence assessment.

Any critical or major issue requires REVISION_NEEDED. Minor issues alone allow PASS.
Never claim a source was checked unless you retrieved it. Do not expose private reasoning.
"""

VERIFIER_INSTRUCTION = """You verify a scientific claim against the indexed paper corpus.
Split compound claims into testable parts. Search metadata and full text with varied
queries for supporting, contradicting, and qualifying evidence. Verify cited paper
metadata with get_paper_metadata. Never invent citations. Distinguish lack of evidence
from evidence of absence, and say when corpus coverage limits the conclusion.

Return a Claim Verification Report with sections: Claim Under Review (exact claim,
verdict and confidence), Corroborating Evidence, Contradicting Evidence, Nuances and
Conditions, Confidence Assessment, and References (full details and paper IDs).
Choose verdict from STRONGLY SUPPORTED, PARTIALLY SUPPORTED, MIXED EVIDENCE,
WEAKLY CONTRADICTED, CONTRADICTED, INSUFFICIENT EVIDENCE; confidence HIGH,
MODERATE, or LOW. Do not expose private reasoning.
"""

_AGENTS = {
    RESEARCHER_AGENT_ID: ("researcher", RESEARCHER_INSTRUCTION),
    REVIEWER_AGENT_ID: ("reviewer", REVIEWER_INSTRUCTION),
    CLAIM_VERIFICATION_AGENT_ID: ("claim_verifier", VERIFIER_INSTRUCTION),
}
_TOOLS = [search_papers, search_metadata, get_paper_metadata,
          top_cited_papers, corpus_overview, publication_trends]


def _make_agent(agent_id: str) -> Agent:
    """Build a role-specific ADK agent after checking Vertex AI configuration."""
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() not in {"true", "1"}:
        raise RuntimeError("Set GOOGLE_GENAI_USE_VERTEXAI=TRUE in .env")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "")
    if not project or project.startswith("your-") or not location:
        raise RuntimeError("Set GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION in .env")
    name, instruction = _AGENTS[agent_id]
    return Agent(name=name, model=GEMINI_MODEL, instruction=instruction, tools=_TOOLS)


async def stream_converse(
    agent_id: str,
    message: str,
    conversation_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Run one ADK agent turn and map ADK events to the existing SSE contract."""
    # The orchestrator supplies drafts and feedback explicitly for revisions.
    # Isolated sessions avoid cross-request and cross-user state leakage.
    try:
        agent = _make_agent(agent_id)
        session_service = InMemorySessionService()
        app_name = "research_agent"
        user_id = "research_request"
        session = await session_service.create_session(app_name=app_name, user_id=user_id)
        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
        content = types.Content(role="user", parts=[types.Part(text=message)])
        chunks: list[str] = []

        async for event in runner.run_async(
            user_id=user_id, session_id=session.id, new_message=content,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            if getattr(event, "error_code", None):
                raise RuntimeError(f"ADK error: {event.error_code}: {event.error_message}")
            parts = event.content.parts if event.content and event.content.parts else []
            for part in parts:
                if part.function_call:
                    call = part.function_call
                    yield {"event": "tool_call", "data": {
                        "tool_id": call.name, "params": call.args or {},
                    }}
                if part.function_response:
                    response = part.function_response
                    yield {"event": "tool_result", "data": {
                        "tool_id": response.name, "results": response.response,
                    }}
            visible_text = "".join(part.text for part in parts
                                   if part.text and not getattr(part, "thought", False))
            if event.is_final_response():
                streamed_text = "".join(chunks)
                if not visible_text:
                    final_text = streamed_text
                elif visible_text.startswith(streamed_text):
                    final_text = visible_text
                elif streamed_text.endswith(visible_text):
                    final_text = streamed_text
                else:
                    final_text = streamed_text + visible_text
                if final_text:
                    if not chunks:
                        yield {"event": "message_chunk", "data": {"text_chunk": final_text}}
                    yield {"event": "message_complete", "data": {"message_content": final_text}}
            elif event.partial and visible_text:
                chunks.append(visible_text)
                yield {"event": "message_chunk", "data": {"text_chunk": visible_text}}
    except Exception as exc:
        logger.exception("ADK agent %s failed", agent_id)
        yield {"event": "error", "data": {"message": f"{type(exc).__name__}: {exc}"}}
