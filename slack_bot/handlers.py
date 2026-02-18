"""Slash command handlers for the Slack research bot."""

import asyncio
import json
import logging

from slack_bolt.async_app import AsyncApp

from server.services.orchestrator import run_research_loop, run_claim_verification
from slack_bot.formatting import md_to_mrkdwn, split_message

logger = logging.getLogger(__name__)


def register_handlers(app: AsyncApp):
    """Register all slash command handlers."""

    @app.command("/research")
    async def handle_research(ack, command, client, respond):
        topic = command.get("text", "").strip()
        if not topic:
            await ack("Please provide a topic: `/research <your topic>`")
            return

        await ack(
            f"Starting research on: *{topic}*\n"
            "This takes 2-8 minutes. I'll post progress updates below."
        )

        # Spawn background task so the HTTP response returns immediately.
        asyncio.create_task(
            _run_research(topic, command, client, respond)
        )

    async def _run_research(topic, command, client, respond):
        """Long-running research task that runs in the background."""
        channel_id = command["channel_id"]
        user_id = command["user_id"]

        try:
            # Post initial status message (becomes the thread parent).
            initial = await client.chat_postMessage(
                channel=channel_id,
                text=(
                    f":mag: *Research Agent* is working on: _{topic}_\n\n"
                    f"Requested by <@{user_id}>"
                ),
            )
            thread_ts = initial["ts"]

            # Track progress lines and the progress message ts.
            progress_lines = []
            progress_ts = None
            report = None
            iteration_info = None

            async for sse_line in run_research_loop(topic):
                if not sse_line.startswith("event: "):
                    continue

                lines = sse_line.strip().split("\n")
                event_type = lines[0].replace("event: ", "")
                data_str = (
                    lines[1].replace("data: ", "") if len(lines) > 1 else "{}"
                )

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                update_text = None

                if event_type == "agent_start":
                    agent = data.get("agent", "Agent")
                    iteration = data.get("iteration", 1)
                    update_text = (
                        f":hourglass_flowing_sand: *{agent}* starting "
                        f"(iteration {iteration})..."
                    )

                elif event_type == "tool_call":
                    tool_id = data.get("tool_id", "unknown")
                    update_text = f":wrench: Using tool: `{tool_id}`"

                elif event_type == "agent_end":
                    agent = data.get("agent", "Agent")
                    update_text = f":white_check_mark: *{agent}* finished."

                elif event_type == "verdict":
                    verdict = data.get("verdict", "")
                    iteration = data.get("iteration", 1)
                    emoji = (
                        ":white_check_mark:"
                        if verdict == "PASS"
                        else ":arrows_counterclockwise:"
                    )
                    update_text = (
                        f"{emoji} *Peer Review Verdict* "
                        f"(iteration {iteration}): `{verdict}`"
                    )

                elif event_type == "result":
                    report = data.get("report")
                    iteration_info = data.get("iteration_info")

                elif event_type == "error":
                    msg = data.get("message", "Unknown error")
                    update_text = f":x: *Error:* {msg}"

                # Update the progress message in the thread.
                if update_text:
                    progress_lines.append(update_text)
                    full_text = "\n".join(progress_lines)
                    if progress_ts:
                        await client.chat_update(
                            channel=channel_id,
                            ts=progress_ts,
                            text=full_text,
                        )
                    else:
                        msg = await client.chat_postMessage(
                            channel=channel_id,
                            thread_ts=thread_ts,
                            text=full_text,
                        )
                        progress_ts = msg["ts"]

            # Mark progress as complete.
            if progress_ts:
                progress_lines.append(
                    "\n:white_check_mark: *Research complete!*"
                )
                await client.chat_update(
                    channel=channel_id,
                    ts=progress_ts,
                    text="\n".join(progress_lines),
                )

            # Post the full report as threaded replies.
            if report:
                mrkdwn_report = md_to_mrkdwn(report)
                parts = split_message(mrkdwn_report, 3900)
                for part in parts:
                    await client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text=part,
                        unfurl_links=False,
                    )

            # Update the parent message to show completion.
            status = iteration_info or "Complete"
            await client.chat_update(
                channel=channel_id,
                ts=thread_ts,
                text=(
                    f":white_check_mark: *Research complete:* _{topic}_\n"
                    f"{status}\n\n"
                    f"See thread for full report. Requested by <@{user_id}>"
                ),
            )

        except Exception:
            logger.exception("Research command failed for topic: %s", topic)
            try:
                await respond(
                    f":x: Something went wrong while researching *{topic}*. "
                    "Please try again."
                )
            except Exception:
                logger.exception("Failed to send error response to Slack")

    @app.command("/check-claim")
    async def handle_verify(ack, command, client, respond):
        claim = command.get("text", "").strip()
        if not claim:
            await ack("Please provide a claim: `/check-claim <your claim>`")
            return

        await ack(
            f"Starting claim verification: *{claim}*\n"
            "This takes 2-3 minutes. I'll post progress updates below."
        )

        asyncio.create_task(
            _run_verification(claim, command, client, respond)
        )

    async def _run_verification(claim, command, client, respond):
        """Long-running verification task that runs in the background."""
        channel_id = command["channel_id"]
        user_id = command["user_id"]

        try:
            initial = await client.chat_postMessage(
                channel=channel_id,
                text=(
                    f":mag: *Claim Verification Agent* is evaluating: _{claim}_\n\n"
                    f"Requested by <@{user_id}>"
                ),
            )
            thread_ts = initial["ts"]

            progress_lines = []
            progress_ts = None
            report = None
            iteration_info = None

            async for sse_line in run_claim_verification(claim):
                if not sse_line.startswith("event: "):
                    continue

                lines = sse_line.strip().split("\n")
                event_type = lines[0].replace("event: ", "")
                data_str = (
                    lines[1].replace("data: ", "") if len(lines) > 1 else "{}"
                )

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                update_text = None

                if event_type == "agent_start":
                    agent = data.get("agent", "Agent")
                    update_text = (
                        f":hourglass_flowing_sand: *{agent}* starting..."
                    )

                elif event_type == "tool_call":
                    tool_id = data.get("tool_id", "unknown")
                    update_text = f":wrench: Using tool: `{tool_id}`"

                elif event_type == "agent_end":
                    agent = data.get("agent", "Agent")
                    update_text = f":white_check_mark: *{agent}* finished."

                elif event_type == "result":
                    report = data.get("report")
                    iteration_info = data.get("iteration_info")

                elif event_type == "error":
                    msg = data.get("message", "Unknown error")
                    update_text = f":x: *Error:* {msg}"

                if update_text:
                    progress_lines.append(update_text)
                    full_text = "\n".join(progress_lines)
                    if progress_ts:
                        await client.chat_update(
                            channel=channel_id,
                            ts=progress_ts,
                            text=full_text,
                        )
                    else:
                        msg = await client.chat_postMessage(
                            channel=channel_id,
                            thread_ts=thread_ts,
                            text=full_text,
                        )
                        progress_ts = msg["ts"]

            if progress_ts:
                progress_lines.append(
                    "\n:white_check_mark: *Verification complete!*"
                )
                await client.chat_update(
                    channel=channel_id,
                    ts=progress_ts,
                    text="\n".join(progress_lines),
                )

            if report:
                mrkdwn_report = md_to_mrkdwn(report)
                parts = split_message(mrkdwn_report, 3900)
                for part in parts:
                    await client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text=part,
                        unfurl_links=False,
                    )

            status = iteration_info or "Complete"
            await client.chat_update(
                channel=channel_id,
                ts=thread_ts,
                text=(
                    f":white_check_mark: *Verification complete:* _{claim}_\n"
                    f"{status}\n\n"
                    f"See thread for full report. Requested by <@{user_id}>"
                ),
            )

        except Exception:
            logger.exception("Verify command failed for claim: %s", claim)
            try:
                await respond(
                    f":x: Something went wrong while verifying *{claim}*. "
                    "Please try again."
                )
            except Exception:
                logger.exception("Failed to send error response to Slack")
