"""
Research Review App — Streamlit frontend for the multi-agent literature review workflow.

Triggers the Research Review Loop workflow via the Kibana API, polls for completion,
and displays the full literature review report and peer review.
"""

import os
import time
import requests
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

KIBANA_URL = os.getenv("KIBANA_URL")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")
WORKFLOW_ID = os.getenv("WORKFLOW_ID")
WORKFLOW_YAML_PATH = Path(__file__).parent / "workflows" / "research_review_loop.yaml"

HEADERS = {
    "Content-Type": "application/json",
    "kbn-xsrf": "true",
    "x-elastic-internal-origin": "Kibana",
    "Authorization": f"ApiKey {ELASTIC_API_KEY}",
}

POLL_INTERVAL = 10  # seconds between status checks


def load_workflow_yaml() -> str:
    """Read the workflow YAML file as a string."""
    return WORKFLOW_YAML_PATH.read_text(encoding="utf-8")


def trigger_workflow(topic: str) -> str:
    """Trigger the Research Review Loop workflow and return the execution ID."""
    url = f"{KIBANA_URL}/api/workflows/test"
    payload = {
        "inputs": {"topic": topic},
        "workflowId": WORKFLOW_ID,
        "workflowYaml": load_workflow_yaml(),
    }
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["workflowExecutionId"]


def get_execution(execution_id: str) -> dict:
    """Fetch the current state of a workflow execution."""
    url = f"{KIBANA_URL}/api/workflowExecutions/{execution_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_step_output(execution: dict, step_id: str) -> str | None:
    """Extract the output from a specific step execution.

    The API returns stepExecutions with:
    - stepId: the step name from the YAML
    - stepType: "ai.agent", "ai.prompt", "console", "if", "step_level_timeout"
    - output: dict with "message" (ai.agent) or "content" (ai.prompt),
              or a plain string (console steps)

    Skip wrapper entries like step_level_timeout.
    """
    for step in execution.get("stepExecutions", []):
        if step.get("stepId") != step_id:
            continue
        # Skip timeout wrappers — they don't have the actual output
        if step.get("stepType") == "step_level_timeout":
            continue

        output = step.get("output")
        if output is None:
            continue

        # Console steps return output as a plain string
        if isinstance(output, str):
            return output

        # ai.agent steps: output.message
        # ai.prompt steps: output.content
        return output.get("message") or output.get("content")

    return None


def find_final_report(execution: dict) -> tuple[str | None, str | None, str | None]:
    """
    Find the best available report and review from the execution.
    Checks v3 -> v2 -> v1 to get the most revised version.
    Returns (report, review, verdict_info).
    """
    # Check iteration 3
    report = extract_step_output(execution, "researcher_draft_v3")
    if report:
        review = extract_step_output(execution, "review_v3")
        return report, review, "Iteration 3 (final revision)"

    # Check iteration 2
    report = extract_step_output(execution, "researcher_draft_v2")
    if report:
        review = extract_step_output(execution, "review_v2")
        verdict = extract_step_output(execution, "parse_verdict_v2")
        return report, review, f"Iteration 2 (verdict: {verdict or 'unknown'})"

    # Check iteration 1
    report = extract_step_output(execution, "researcher_draft_v1")
    if report:
        review = extract_step_output(execution, "review_v1")
        verdict = extract_step_output(execution, "parse_verdict_v1")
        return report, review, f"Iteration 1 (verdict: {verdict or 'unknown'})"

    return None, None, None


def get_iteration_summary(execution: dict) -> list[str]:
    """Build a summary of which iterations ran and their verdicts."""
    summary = []
    v1 = extract_step_output(execution, "parse_verdict_v1")
    if v1:
        summary.append(f"Iteration 1: {v1}")
    v2 = extract_step_output(execution, "parse_verdict_v2")
    if v2:
        summary.append(f"Iteration 2: {v2}")
    v3_review = extract_step_output(execution, "review_v3")
    if v3_review:
        summary.append("Iteration 3: Final review completed")
    return summary


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Research Review Agent", page_icon="📚", layout="wide")

st.title("Multi-Agent Literature Review")
st.caption(
    "Powered by Elastic Agent Builder — Researcher Agent + Peer Review Agent "
    "orchestrated via Elastic Workflows"
)

topic = st.text_area(
    "Enter a research topic",
    placeholder="e.g. Planning and reasoning capabilities in AI agent systems",
    height=80,
)

if st.button("Run Literature Review", type="primary", disabled=not topic.strip()):
    with st.status("Running multi-agent workflow...", expanded=True) as status:
        # 1. Trigger
        st.write("Triggering Research Review Loop workflow...")
        try:
            execution_id = trigger_workflow(topic.strip())
        except requests.HTTPError as e:
            st.error(f"Failed to trigger workflow: {e.response.status_code} — {e.response.text}")
            st.stop()
        except Exception as e:
            st.error(f"Failed to trigger workflow: {e}")
            st.stop()

        st.write(f"Execution ID: `{execution_id}`")

        # 2. Poll until complete
        st.write("Waiting for workflow to complete...")
        while True:
            time.sleep(POLL_INTERVAL)
            try:
                execution = get_execution(execution_id)
            except Exception as e:
                st.warning(f"Poll error (retrying): {e}")
                continue

            current_status = execution.get("status", "unknown")
            step_count = len(execution.get("stepExecutions", []))
            st.write(f"Status: **{current_status}** — {step_count} steps completed")

            if current_status in ("completed", "failed", "error"):
                break

        if current_status != "completed":
            status.update(label="Workflow failed", state="error")
            st.error(f"Workflow ended with status: {current_status}")
            with st.expander("Raw execution data"):
                st.json(execution)
            st.stop()

        status.update(label="Workflow complete!", state="complete")

    # 3. Extract results
    report, review, iteration_info = find_final_report(execution)
    iterations = get_iteration_summary(execution)

    # 4. Display iteration info
    if iterations:
        st.subheader("Review Loop Summary")
        for item in iterations:
            st.write(f"- {item}")
        if iteration_info:
            st.write(f"**Final report from:** {iteration_info}")
        st.divider()

    # 5. Display report
    if report:
        st.subheader("Literature Review Report")
        st.markdown(report)
    else:
        st.warning("No report content found in the workflow execution.")
        with st.expander("Raw execution data"):
            st.json(execution)

    # 6. Display peer review
    if review:
        with st.expander("Peer Review Feedback"):
            st.markdown(review)

    # 7. Raw data for debugging
    with st.expander("Raw execution data (debug)"):
        st.json(execution)
