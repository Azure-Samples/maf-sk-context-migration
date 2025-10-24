"""Microsoft Agent Framework conversation runner for scenario-based demos."""
from __future__ import annotations

import inspect
from typing import Any, Dict, List

from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

try:
    from agent_framework import ChatAgent
    from agent_framework.azure import AzureAIAgentClient
except ImportError as exc:  # pragma: no cover - surface dependency issues faster
    raise SystemExit(
        "The 'agent_framework' package is required for this demonstration. Install it with 'pip install agent-framework-core'."
    ) from exc

from agent_conversation.scenario_definitions import ScenarioConfig
from agent_conversation.strategy import FrameworkConversationResult
from agent_conversation.tools import (
    AGENT_FRAMEWORK_TOOLS,
    OperationTracker,
    ensure_env,
    evaluate_workforce_tool,
    get_daily_staff_tool,
    get_staff_schedule_tool,
    get_staff_updates_tool,
    log_event,
    log_summary,
    summarise_metrics,
    store_context_tool,
)


load_dotenv()

FRAMEWORK_LABEL = "Agent Framework"


def validate_azure_agent_env() -> None:
    """Ensure the Azure AI Agent environment variables are available."""

    ensure_env("AZURE_AI_PROJECT_ENDPOINT")
    ensure_env("AZURE_AI_MODEL_DEPLOYMENT_NAME")


async def resolve_tool_output(result: Any) -> Any:
    """Resolve coroutine results returned by Agent Framework tool calls."""

    if inspect.isawaitable(result):
        return await result
    return result


def response_to_text(response: Any) -> str:
    """Convert Agent Framework responses to plain text."""

    messages = getattr(response, "messages", [])
    if not messages:
        return str(response)
    collected: List[str] = []
    for message in messages:
        for item in getattr(message, "contents", []):
            text = getattr(item, "text", None)
            if text:
                collected.append(text)
    return "\n".join(collected) if collected else str(response)


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


def _summarise_forward_staffing(schedule: Dict[str, Any], updates: Dict[str, Any], horizon: int) -> str:
    staff_entries = schedule.get("staff_schedule", [])
    updates_entries = updates.get("staff_updates", [])
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
        day_staff = [entry for entry in staff_entries if entry.get("date") == day]
        roles = {entry.get("role") for entry in day_staff}
        lines.append(f"- {day}: {len(day_staff)} assignments covering roles {sorted(roles)}")
    flagged_updates = [update for update in updates_entries if update.get("update_type", "").lower() in {"absence", "shift change"}]
    if flagged_updates:
        lines.append("Recent updates to consider:")
        for update in flagged_updates[:5]:
            lines.append(
                f"  * {update.get('date')} - {update.get('name')}: {update.get('update_type')} ({update.get('details')})"
            )
    return "\n".join(lines)


async def _build_scenario_brief(scenario: ScenarioConfig) -> Dict[str, Any]:
    if scenario.identifier == "coverage_assessment":
        payload = await resolve_tool_output(evaluate_workforce_tool(date=scenario.target_date))
        return {
            "coverage_payload": payload,
            "brief": _summarise_coverage_insights(payload),
        }

    schedule = await resolve_tool_output(get_staff_schedule_tool())
    updates = await resolve_tool_output(get_staff_updates_tool())
    # Include a quick look at the specified target date to ground the conversation
    sample_day = await resolve_tool_output(get_daily_staff_tool(scenario.target_date))
    return {
        "schedule_snapshot": schedule,
        "updates_snapshot": updates,
        "daily_staff": sample_day,
        "brief": _summarise_forward_staffing(schedule, updates, scenario.planning_horizon_days),
    }


async def run_agent_framework_conversation(scenario: ScenarioConfig) -> FrameworkConversationResult:
    """Execute the Agent Framework conversation for the provided scenario."""

    validate_azure_agent_env()
    tracker = OperationTracker()

    with tracker.span(
        FRAMEWORK_LABEL,
        "Context",
        "Load scenario brief",
        lambda: {"id": scenario.identifier},
    ):
        context_payload = await _build_scenario_brief(scenario)
    shared_context: Dict[str, Any] = {"scenario": scenario.identifier, "summary": context_payload.get("brief")}

    transcript: List[Dict[str, Any]] = []

    async with DefaultAzureCredential() as credential:
        async with AzureAIAgentClient(async_credential=credential) as client:
            facilitator = ChatAgent(
                name="Facilitator",
                chat_client=client,
                instructions=scenario.agent_framework.facilitator_instructions,
                tools=AGENT_FRAMEWORK_TOOLS,
            )
            expert = ChatAgent(
                name="Specialist",
                chat_client=client,
                instructions=scenario.agent_framework.expert_instructions,
                tools=AGENT_FRAMEWORK_TOOLS,
            )

            facilitator_thread = facilitator.get_new_thread()
            expert_thread = expert.get_new_thread()

            kickoff_message = scenario.agent_framework.kickoff_message
            with tracker.span(
                FRAMEWORK_LABEL,
                "Interaction",
                "Facilitator kickoff",
                lambda: {"thread": getattr(facilitator_thread, "id", "local")},
            ):
                facilitator_result = await facilitator.run(kickoff_message, thread=facilitator_thread)
                facilitator_text = response_to_text(facilitator_result)
                shared_context = await resolve_tool_output(
                    store_context_tool(shared_context, "facilitator_summary", facilitator_text)
                )
                log_event(
                    FRAMEWORK_LABEL,
                    facilitator.name or "Facilitator",
                    facilitator_text,
                    {"thread_id": getattr(facilitator_thread, "id", "local"), **shared_context},
                )
                transcript.append(
                    {
                        "speaker": facilitator.name or "Facilitator",
                        "thread": str(getattr(facilitator_thread, "id", "local")),
                        "message": facilitator_text,
                    },
                )

            with tracker.span(
                FRAMEWORK_LABEL,
                "Interaction",
                "Specialist response",
                lambda: {"thread": getattr(expert_thread, "id", "local")},
            ):
                expert_result = await expert.run(facilitator_text, thread=expert_thread)
                expert_text = response_to_text(expert_result)
                shared_context = await resolve_tool_output(
                    store_context_tool(shared_context, "specialist_response", expert_text)
                )
                log_event(
                    FRAMEWORK_LABEL,
                    expert.name or "Specialist",
                    expert_text,
                    {"thread_id": getattr(expert_thread, "id", "local"), **shared_context},
                )
                transcript.append(
                    {
                        "speaker": expert.name or "Specialist",
                        "thread": str(getattr(expert_thread, "id", "local")),
                        "message": expert_text,
                    },
                )

            follow_up = scenario.agent_framework.expert_follow_up
            with tracker.span(
                FRAMEWORK_LABEL,
                "Interaction",
                "Specialist follow-up",
                lambda: {"thread": getattr(expert_thread, "id", "local")},
            ):
                expert_follow_up_result = await expert.run(follow_up, thread=expert_thread)
                expert_follow_up_text = response_to_text(expert_follow_up_result)
                shared_context = await resolve_tool_output(
                    store_context_tool(shared_context, "follow_up", expert_follow_up_text)
                )
                log_event(
                    FRAMEWORK_LABEL,
                    expert.name or "Specialist",
                    expert_follow_up_text,
                    {"thread_id": getattr(expert_thread, "id", "local"), **shared_context},
                )
                transcript.append(
                    {
                        "speaker": expert.name or "Specialist",
                        "thread": str(getattr(expert_thread, "id", "local")),
                        "message": expert_follow_up_text,
                    },
                )

            wrap_up_prompt = scenario.agent_framework.facilitator_wrap_up
            with tracker.span(
                FRAMEWORK_LABEL,
                "Interaction",
                "Facilitator wrap-up",
                lambda: {"thread": getattr(facilitator_thread, "id", "local")},
            ):
                facilitator_wrap_up_result = await facilitator.run(wrap_up_prompt, thread=facilitator_thread)
                facilitator_wrap_up_text = response_to_text(facilitator_wrap_up_result)
                shared_context = await resolve_tool_output(
                    store_context_tool(shared_context, "wrap_up", facilitator_wrap_up_text)
                )
                log_event(
                    FRAMEWORK_LABEL,
                    facilitator.name or "Facilitator",
                    facilitator_wrap_up_text,
                    {"thread_id": getattr(facilitator_thread, "id", "local"), **shared_context},
                )
                transcript.append(
                    {
                        "speaker": facilitator.name or "Facilitator",
                        "thread": str(getattr(facilitator_thread, "id", "local")),
                        "message": facilitator_wrap_up_text,
                    },
                )

    metrics = summarise_metrics(tracker)
    log_summary(tracker)

    shared_context.update({"scenario_brief": context_payload.get("brief")})
    return FrameworkConversationResult(
        framework=FRAMEWORK_LABEL,
        transcript=transcript,
        context_snapshot=shared_context,
        metrics=metrics,
    )
