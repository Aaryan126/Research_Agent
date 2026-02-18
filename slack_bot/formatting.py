"""Convert Markdown to Slack mrkdwn format and split long messages."""

import re


def md_to_mrkdwn(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn.

    Handles headers, bold, links. Leaves code blocks untouched.
    """
    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        # Headers: # Title -> *Title*
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            result.append(f"\n*{header_match.group(2)}*")
            continue

        # Bold: **text** -> *text*
        line = re.sub(r"\*\*(.+?)\*\*", r"*\1*", line)

        # Links: [text](url) -> <url|text>
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", line)

        result.append(line)

    return "\n".join(result)


def split_message(text: str, limit: int = 3900) -> list[str]:
    """Split a long message into chunks that fit Slack's character limit.

    Splits on paragraph boundaries (double newlines) where possible,
    falling back to single newlines, then hard-truncating.
    """
    if len(text) <= limit:
        return [text]

    parts = []
    remaining = text

    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break

        # Try to split at a paragraph boundary.
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit

        parts.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")

    return parts
