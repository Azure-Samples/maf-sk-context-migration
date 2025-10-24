"""Entry point executing scenario-driven agent conversations."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List

from agent_conversation.scenario_strategies import select_strategies
from agent_conversation.strategy import ConversationStrategy, ScenarioResult


async def execute_async(selection: str | None = None) -> Dict[str, Any]:
    """Execute the selected scenario strategies asynchronously."""

    strategies: Iterable[ConversationStrategy] = select_strategies(selection)

    results: List[ScenarioResult] = []
    for strategy in strategies:
        results.append(await strategy.execute())

    response: Dict[str, Any] = {}
    combined_metrics: List[Dict[str, Any]] = []
    for result in results:
        scenario_payload = result.as_dict()
        response[result.identifier] = scenario_payload
        for conversation in scenario_payload["conversations"]:
            combined_metrics.extend(conversation.get("metrics", []))

    response["summary"] = combined_metrics
    return response


def execute(selection: str | None = None) -> Dict[str, Any]:
    """Synchronously execute the scenario strategies and collect results."""

    return asyncio.run(execute_async(selection))


def _capture_logs() -> tuple[StringIO, logging.Handler]:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    return stream, handler


def _write_markdown(output: Dict[str, Any], logs: str) -> None:
    target_path = Path(__file__).with_name("comparison_result.md")
    markdown_lines = [
        "# Agent Conversation Comparison",
        "",
        "## Output",
        "```json",
        json.dumps(output, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Logs",
        "```text",
        logs.strip(),
        "```",
        "",
    ]
    target_path.write_text("\n".join(markdown_lines), encoding="utf-8")


def main() -> None:
    """Run the requested scenarios and print their combined output as JSON."""

    selection = os.getenv("AGENT_SCENARIO_SELECTION", "random")
    log_stream, handler = _capture_logs()
    try:
        output = execute(selection)
    finally:
        logging.getLogger().removeHandler(handler)
    logs = log_stream.getvalue()
    _write_markdown(output, logs)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
