"""Semantic Kernel conversation runner for scenario-based demonstrations."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Dict, List, cast

from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
from semantic_kernel.agents.open_ai.run_polling_options import RunPollingOptions

from .scenario_definitions import ScenarioConfig
from .strategy import FrameworkConversationResult
from .tools import (
    ConversationToolsPlugin,
    OperationTracker,
    log_event,
    log_summary,
    summarise_metrics,
    to_plain_text,
)


load_dotenv()

FRAMEWORK_LABEL = "Semantic Kernel"
DEFAULT_POLLING_TIMEOUT_SECONDS = 180


def ensure_azure_ai_settings() -> AzureAIAgentSettings:
    """Resolve Azure AI Agent settings from environment variables."""

    from .tools import ensure_env

    endpoint = ensure_env("AZURE_AI_PROJECT_ENDPOINT")
    deployment = ensure_env("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    return AzureAIAgentSettings(endpoint=endpoint, model_deployment_name=deployment)


def _resolve_polling_options() -> RunPollingOptions:
    raw_timeout: str | None = os.getenv("AZURE_AI_AGENT_POLLING_TIMEOUT_SECONDS")
    timeout_seconds = DEFAULT_POLLING_TIMEOUT_SECONDS
    if raw_timeout:
        try:
            timeout_seconds = max(int(raw_timeout), 1)
        except ValueError as exc:  # pragma: no cover - configuration guard
            raise RuntimeError(
                "AZURE_AI_AGENT_POLLING_TIMEOUT_SECONDS must be an integer representing seconds."
            ) from exc
    return RunPollingOptions(run_polling_timeout=timedelta(seconds=timeout_seconds))


def extract_text_from_response(response: Any) -> str:
    """Normalise the textual payload returned by Azure AI Agents."""

    message = getattr(response, "message", None)
    if message is not None:
        text = getattr(message, "content", None)
        if isinstance(text, str) and text:
            return text
        items = getattr(message, "items", None) or []
        if items:
            return to_plain_text(items)
    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text
    items = getattr(response, "items", None) or []
    if items:
        return to_plain_text(items)
    return str(response)


@asynccontextmanager
async def azure_ai_agent_client(settings: AzureAIAgentSettings):
    """Create an Azure AI Agent client using managed credentials."""

    async with DefaultAzureCredential() as credential:
        async with AzureAIAgent.create_client(credential=credential, endpoint=settings.endpoint) as client:
            yield client


async def create_agent(
    client,
    settings: AzureAIAgentSettings,
    name: str,
    instructions: str,
    plugin: ConversationToolsPlugin | None = None,
    polling_options: RunPollingOptions | None = None,
):
    """Provision an agent in the Azure AI Agent service and return an SDK wrapper."""

    deployment = getattr(settings, "model_deployment_name", None) or getattr(settings, "deployment_name", None)
    definition = await client.agents.create_agent(
        model=deployment,
        name=name,
        instructions=instructions,
    )
    plugin_payload: Dict[str, object] | None = None
    if plugin:
        plugin_payload = {"conversation_tools": cast(object, plugin)}
    return AzureAIAgent(
        client=client,
        definition=definition,
        plugins=plugin_payload,
        polling_options=polling_options or _resolve_polling_options(),
    )


async def cleanup_agent(client, agent, thread) -> None:
    """Remove remote artefacts created for the conversation."""

    if thread is not None:
        await thread.delete()
    agent_id = getattr(agent, "id", None) or getattr(getattr(agent, "definition", None), "id", None)
    if agent_id:
        await client.agents.delete_agent(agent_id)


def _summarise_coverage_insights(payload: Dict[str, Any]) -> str:
    insights = payload.get("insights", [])
    if not insights:
        return "No coverage gaps were reported."
    lines: List[str] = []
    for insight in insights[:3]:
        lines.append(
            " | ".join(
                [
                    str(insight.get("date")),
                    str(insight.get("shift")),
                    str(insight.get("role")),
                    insight.get("recommendation", "No recommendation provided."),
                ]
            )
        )
    return "\n".join(lines)


def _summarise_forward_staffing(schedule: Dict[str, Any], horizon: int) -> str:
    staff_entries = schedule.get("staff_schedule", [])
    if not staff_entries:
        return "Staffing schedule is empty; please verify the dataset."
    horizon_dates: Dict[str, int] = {}
    for entry in staff_entries:
        horizon_dates.setdefault(entry.get("date"), 0)
        horizon_dates[entry.get("date")] += 1
    sorted_dates = sorted(horizon_dates)[:horizon]
    lines: List[str] = [
        "Constraints: max 10 hours/day, max 8 consecutive hours, max 5 consecutive days",
        "Upcoming staffing snapshot:",
    ]
    for day in sorted_dates:
        roles = {entry.get("role") for entry in staff_entries if entry.get("date") == day}
        lines.append(f"- {day}: roles {sorted(roles)}")
    return "\n".join(lines)


async def _prepare_context(plugin: ConversationToolsPlugin, scenario: ScenarioConfig) -> Dict[str, Any]:
    if scenario.identifier == "coverage_assessment":
        payload = await plugin.evaluate_workforce(date=scenario.target_date)
        return {
            "coverage_payload": payload,
            "brief": _summarise_coverage_insights(payload),
        }

    schedule = await plugin.get_staff_schedule()
    return {
        "schedule_payload": schedule,
        "brief": _summarise_forward_staffing(schedule, scenario.planning_horizon_days),
    }


async def run_semantic_kernel_conversation(scenario: ScenarioConfig) -> FrameworkConversationResult:
    """Execute the Semantic Kernel conversation for the provided scenario."""

    tracker = OperationTracker()
    settings = ensure_azure_ai_settings()
    plugin = ConversationToolsPlugin()
    polling_options = _resolve_polling_options()

    with tracker.span(FRAMEWORK_LABEL, "Context", "Load scenario context", lambda: {"id": scenario.identifier}):
        context_payload = await _prepare_context(plugin, scenario)

    shared_context: Dict[str, Any] = {"scenario": scenario.identifier, "summary": context_payload.get("brief")}

    transcript: List[Dict[str, Any]] = []

    async with azure_ai_agent_client(settings) as client:
        researcher = await create_agent(
            client,
            settings,
            name="Researcher",
            instructions=scenario.semantic_kernel.researcher_instructions,
            plugin=plugin,
            polling_options=polling_options,
        )
        planner = await create_agent(
            client,
            settings,
            name="Planner",
            instructions=scenario.semantic_kernel.planner_instructions,
            plugin=plugin,
            polling_options=polling_options,
        )

        researcher_thread = None
        planner_thread = None

        try:
            kickoff_prompt = scenario.semantic_kernel.kickoff_message
            log_event(FRAMEWORK_LABEL, "Orchestrator", kickoff_prompt, shared_context)
            with tracker.span(
                FRAMEWORK_LABEL,
                "Interaction",
                "Research kickoff",
                lambda: {"context_keys": sorted(shared_context.keys())},
            ):
                response = await researcher.get_response(messages=kickoff_prompt, thread=researcher_thread)
                researcher_thread = response.thread
                researcher_text = extract_text_from_response(response)
                shared_context = plugin.store_context(shared_context, "research", researcher_text)
                log_event(FRAMEWORK_LABEL, researcher.name or "Researcher", researcher_text, shared_context)
                transcript.append(
                    {
                        "speaker": researcher.name or "Researcher",
                        "message": researcher_text,
                        "thread": getattr(researcher_thread, "id", "local"),
                    },
                )

            with tracker.span(
                FRAMEWORK_LABEL,
                "Interaction",
                "Planning",
                lambda: {"context_keys": sorted(shared_context.keys())},
            ):
                response_plan = await planner.get_response(messages=researcher_text, thread=planner_thread)
                planner_thread = response_plan.thread
                planner_text = extract_text_from_response(response_plan)
                shared_context = plugin.store_context(shared_context, "plan", planner_text)
                log_event(FRAMEWORK_LABEL, planner.name or "Planner", planner_text, shared_context)
                transcript.append(
                    {
                        "speaker": planner.name or "Planner",
                        "message": planner_text,
                        "thread": getattr(planner_thread, "id", "local"),
                    },
                )

            follow_up_prompt = scenario.semantic_kernel.follow_up_prompt
            with tracker.span(
                FRAMEWORK_LABEL,
                "Interaction",
                "Research follow-up",
                lambda: {"context_keys": sorted(shared_context.keys())},
            ):
                response_follow_up = await researcher.get_response(messages=follow_up_prompt, thread=researcher_thread)
                researcher_thread = response_follow_up.thread
                researcher_follow_up_text = extract_text_from_response(response_follow_up)
                shared_context = plugin.store_context(shared_context, "follow_up", researcher_follow_up_text)
                log_event(
                    FRAMEWORK_LABEL,
                    researcher.name or "Researcher",
                    researcher_follow_up_text,
                    shared_context,
                )
                transcript.append(
                    {
                        "speaker": researcher.name or "Researcher",
                        "message": researcher_follow_up_text,
                        "thread": getattr(researcher_thread, "id", "local"),
                    },
                )
        finally:
            await cleanup_agent(client, researcher, researcher_thread)
            await cleanup_agent(client, planner, planner_thread)

    metrics = summarise_metrics(tracker)
    log_summary(tracker)

    shared_context.update({"scenario_brief": context_payload.get("brief")})
    return FrameworkConversationResult(
        framework=FRAMEWORK_LABEL,
        transcript=transcript,
        context_snapshot=shared_context,
        metrics=metrics,
    )
