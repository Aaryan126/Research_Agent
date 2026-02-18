"""Core workflow logic — extracted from app.py (lines 32-133)."""

import requests

from server.config import KIBANA_URL, HEADERS, WORKFLOW_ID, WORKFLOW_YAML_PATH


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
        if step.get("stepType") == "step_level_timeout":
            continue

        output = step.get("output")
        if output is None:
            continue

        if isinstance(output, str):
            return output

        return output.get("message") or output.get("content")

    return None


def find_final_report(execution: dict) -> tuple[str | None, str | None, str | None]:
    """Find the best available report and review from the execution.

    Checks v3 -> v2 -> v1 to get the most revised version.
    Returns (report, review, verdict_info).
    """
    report = extract_step_output(execution, "researcher_draft_v3")
    if report:
        review = extract_step_output(execution, "review_v3")
        return report, review, "Iteration 3 (final revision)"

    report = extract_step_output(execution, "researcher_draft_v2")
    if report:
        review = extract_step_output(execution, "review_v2")
        verdict = extract_step_output(execution, "parse_verdict_v2")
        return report, review, f"Iteration 2 (verdict: {verdict or 'unknown'})"

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
