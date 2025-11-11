"""Microsoft Agent Framework workflow demo using official Python APIs.

This module constructs two workflows using the Microsoft Agent Framework
`WorkflowBuilder`. The workflows demonstrate how to compose Microsoft Agent
Framework chat agents, AI functions, and MCP tools without relying on custom
workflow infrastructure.
"""

import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Dict

from agent_framework import (
    AgentExecutorResponse,
    ChatAgent,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowOutputEvent,
    executor,
)
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential
from typing_extensions import Never

from app.tools import (
    create_cosmos_updates_mcp_tool,
    create_schedule_mcp_tool,
    ensure_env,
    fetch_public_api,
    read_local_playbook,
)

DEFAULT_JOB = "schedule_allocation"
DEFAULT_TARGET_DATE = "2025-11-15"
WORKFLOW_OPTIONS = {
    "quick_schedule_review",
    "schedule_allocation_end_to_end"
}

SCHEDULE_AGENT_INSTRUCTIONS = (
    "You are a workforce schedule analyst. Use the MCP bridge to retrieve the "
    "staffing schedule for the requested job and highlight any resource "
    "conflicts or noteworthy constraints. Keep the response concise and actionable."
)

DATA_FUSION_AGENT_INSTRUCTIONS = (
    "You are a data fusion specialist. Combine the latest schedule insights with "
    "external incident data accessed via HTTPS and Cosmos MCP feeds. Call the "
    "provided tools to reference the incident feed and the coverage deltas, then "
    "summarise actionable follow-ups."
)

DOCUMENT_AGENT_INSTRUCTIONS = (
    "You are a knowledge specialist. Read the local allocation playbook and "
    "summarise the guidance relevant to the detected incidents. Reference concrete "
    "steps that the operations team should follow."
)

ORCHESTRATOR_AGENT_INSTRUCTIONS = (
    "You orchestrate mitigation activities. Given the quick assessment summary, "
    "produce a coordinated plan that assigns owners, timelines, and contingency "
    "actions. Be specific and concise."
)

REPORTER_AGENT_INSTRUCTIONS = (
    "You prepare the final allocation report. Consolidate the orchestrator plan "
    "with the original quick assessment so stakeholders can see the end-to-end "
    "decision trail."
)


@dataclass
class AgentRoster:
    """Bundle of chat agents used across the workflows."""

    schedule: ChatAgent
    data_fusion: ChatAgent
    document: ChatAgent
    orchestrator: ChatAgent
    reporter: ChatAgent


@executor(id="seed_quick")
async def seed_quick_prompt(payload: Dict[str, Any], ctx: WorkflowContext[str]) -> None:
    state = await ctx.get_state() or {}
    job = payload.get("job", DEFAULT_JOB)
    target_date = payload.get("target_date", DEFAULT_TARGET_DATE)
    state.update({"job": job, "target_date": target_date})
    await ctx.set_state(state)

    prompt = (
        "Review the staffing schedule for {date} and outline gaps for job '{job}'. "
        "Confirm hours, coverage, and any critical shifts."
    ).format(date=target_date, job=job)
    await ctx.send_message(prompt)


@executor(id="capture_schedule_summary")
async def capture_schedule_summary(
    response: AgentExecutorResponse, ctx: WorkflowContext[str]
) -> None:
    state = await ctx.get_state() or {}
    summary = _agent_response_to_text(response)
    state["schedule_summary"] = summary
    await ctx.set_state(state)

    target_date = state.get("target_date", DEFAULT_TARGET_DATE)
    follow_up = (
        "Correlate the schedule insights for {date} with live incident data. "
        "Use the HTTPS incident feed and Cosmos MCP tools to flag conflicts."
    ).format(date=target_date)
    await ctx.send_message(follow_up)


@executor(id="capture_data_summary")
async def capture_data_summary(
    response: AgentExecutorResponse, ctx: WorkflowContext[str]
) -> None:
    state = await ctx.get_state() or {}
    assessment = _agent_response_to_text(response)
    state["data_notes"] = assessment
    await ctx.set_state(state)

    await ctx.send_message(
        "Consult the allocation playbook for mitigation guidance relevant to the "
        "detected incidents."
    )


@executor(id="capture_playbook_guidance")
async def capture_playbook_guidance(
    response: AgentExecutorResponse, ctx: WorkflowContext[dict[str, Any]]
) -> None:
    state = await ctx.get_state() or {}
    state["playbook_guidance"] = _agent_response_to_text(response)

    summary = {
        "schedule_summary": state.get("schedule_summary", ""),
        "external_findings": state.get("data_notes", ""),
        "playbook_guidance": state.get("playbook_guidance", ""),
    }
    state["quick_summary"] = summary
    await ctx.set_state(state)
    await ctx.send_message(summary)


@executor(id="emit_quick_summary")
async def emit_quick_summary(
    summary: dict[str, Any], ctx: WorkflowContext[Never, dict[str, Any]]
) -> None:
    await ctx.yield_output(summary)


@executor(id="stage_orchestration_prompt")
async def stage_orchestration_prompt(
    summary: dict[str, Any], ctx: WorkflowContext[str]
) -> None:
    state = await ctx.get_state() or {}
    state["quick_summary"] = summary
    await ctx.set_state(state)

    formatted = _format_quick_summary(summary)
    prompt = (
        "Use the quick assessment below to coordinate mitigation steps.\n\n"
        f"{formatted}"
    )
    await ctx.send_message(prompt)


@executor(id="capture_orchestrator_guidance")
async def capture_orchestrator_guidance(
    response: AgentExecutorResponse, ctx: WorkflowContext[str]
) -> None:
    state = await ctx.get_state() or {}
    orchestration_notes = _agent_response_to_text(response)
    state["orchestration_notes"] = orchestration_notes
    await ctx.set_state(state)

    formatted = _format_quick_summary(state.get("quick_summary", {}))
    prompt = (
        "Produce a final allocation report that references:\n"
        "- Quick assessment findings\n"
        "- Orchestration plan and owners\n\n"
        f"Quick assessment:\n{formatted}\n\n"
        f"Orchestration notes:\n{orchestration_notes}"
    )
    await ctx.send_message(prompt)


@executor(id="collect_final_report")
async def collect_final_report(
    response: AgentExecutorResponse, ctx: WorkflowContext[Never, dict[str, Any]]
) -> None:
    state = await ctx.get_state() or {}
    final_report = _agent_response_to_text(response)
    payload = {
        "quick_assessment": state.get("quick_summary", {}),
        "orchestration_notes": state.get("orchestration_notes", ""),
        "final_report": final_report,
    }
    await ctx.yield_output(payload)


def _agent_response_to_text(response: AgentExecutorResponse) -> str:
    chunks: list[str] = []
    agent_response = getattr(response, "agent_run_response", None)
    for message in getattr(agent_response, "messages", []):
        for content in getattr(message, "contents", []):
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _format_quick_summary(summary: Dict[str, Any]) -> str:
    if not summary:
        return "No quick assessment data captured."
    parts: list[str] = []
    for key, value in summary.items():
        if not value:
            continue
        label = key.replace("_", " ").title()
        parts.append(f"{label}: {value}")
    return "\n".join(parts)


def build_quick_workflow(roster: AgentRoster) -> Workflow:
    return (
        WorkflowBuilder(name="quick_schedule_review")
        .set_start_executor(seed_quick_prompt)
        .add_edge(seed_quick_prompt, roster.schedule)
        .add_edge(roster.schedule, capture_schedule_summary)
        .add_edge(capture_schedule_summary, roster.data_fusion)
        .add_edge(roster.data_fusion, capture_data_summary)
        .add_edge(capture_data_summary, roster.document)
        .add_edge(roster.document, capture_playbook_guidance)
        .add_edge(capture_playbook_guidance, emit_quick_summary)
        .build()
    )


def build_allocation_workflow(roster: AgentRoster) -> Workflow:
    return (
        WorkflowBuilder(name="schedule_allocation_end_to_end")
        .set_start_executor(seed_quick_prompt)
        .add_edge(seed_quick_prompt, roster.schedule)
        .add_edge(roster.schedule, capture_schedule_summary)
        .add_edge(capture_schedule_summary, roster.data_fusion)
        .add_edge(roster.data_fusion, capture_data_summary)
        .add_edge(capture_data_summary, roster.document)
        .add_edge(roster.document, capture_playbook_guidance)
        .add_edge(capture_playbook_guidance, stage_orchestration_prompt)
        .add_edge(stage_orchestration_prompt, roster.orchestrator)
        .add_edge(roster.orchestrator, capture_orchestrator_guidance)
        .add_edge(capture_orchestrator_guidance, roster.reporter)
        .add_edge(roster.reporter, collect_final_report)
        .build()
    )


async def run_workflow(workflow: Workflow, payload: Dict[str, Any]) -> Dict[str, Any]:
    final_payload: Dict[str, Any] | None = None
    async for event in workflow.run_stream(payload):
        if isinstance(event, WorkflowOutputEvent):
            final_payload = event.data
    if final_payload is None:
        raise RuntimeError("Workflow completed without producing a WorkflowOutputEvent.")
    return final_payload


async def create_agent_roster(stack: AsyncExitStack, enable_mcp: bool) -> AgentRoster:
    credential = await stack.enter_async_context(AzureCliCredential())
    client = await stack.enter_async_context(AzureAIAgentClient(async_credential=credential))

    schedule_tools = [fetch_public_api]
    data_fusion_tools = [fetch_public_api]

    if enable_mcp:
        schedule_tools.append(create_schedule_mcp_tool())
        data_fusion_tools.append(create_cosmos_updates_mcp_tool())

    document_tools = [read_local_playbook]

    schedule_agent = await stack.enter_async_context(
        ChatAgent(
            name="Schedule Analyst",
            chat_client=client,
            instructions=SCHEDULE_AGENT_INSTRUCTIONS,
            tools=schedule_tools,
        )
    )

    data_agent = await stack.enter_async_context(
        ChatAgent(
            name="Data Fusion Analyst",
            chat_client=client,
            instructions=DATA_FUSION_AGENT_INSTRUCTIONS,
            tools=data_fusion_tools,
        )
    )

    document_agent = await stack.enter_async_context(
        ChatAgent(
            name="Knowledge Specialist",
            chat_client=client,
            instructions=DOCUMENT_AGENT_INSTRUCTIONS,
            tools=document_tools,
        )
    )

    orchestrator_agent = await stack.enter_async_context(
        ChatAgent(
            name="Workflow Orchestrator",
            chat_client=client,
            instructions=ORCHESTRATOR_AGENT_INSTRUCTIONS,
        )
    )

    reporter_agent = await stack.enter_async_context(
        ChatAgent(
            name="Operations Reporter",
            chat_client=client,
            instructions=REPORTER_AGENT_INSTRUCTIONS,
        )
    )

    return AgentRoster(
        schedule=schedule_agent,
        data_fusion=data_agent,
        document=document_agent,
        orchestrator=orchestrator_agent,
        reporter=reporter_agent,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Microsoft Agent Framework workflow demo")
    parser.add_argument(
        "--workflow",
        choices=sorted(WORKFLOW_OPTIONS),
        default="schedule_allocation_end_to_end",
        help="Workflow identifier to execute.",
    )
    parser.add_argument("--job", default=DEFAULT_JOB, help="Job identifier used by seed prompt.")
    parser.add_argument(
        "--target-date",
        default=DEFAULT_TARGET_DATE,
        dest="target_date",
        help="Target date for the allocation scenario (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--disable-mcp",
        action="store_true",
        help="Skip attaching MCP tools when running the workflow.",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> Dict[str, Any]:
    ensure_env("AZURE_AI_PROJECT_ENDPOINT")
    ensure_env("AZURE_AI_MODEL_DEPLOYMENT_NAME")

    payload = {"job": args.job, "target_date": args.target_date}

    async with AsyncExitStack() as stack:
        roster = await create_agent_roster(stack, enable_mcp=not args.disable_mcp)

        if args.workflow == "quick_schedule_review":
            workflow = build_quick_workflow(roster)
        else:
            workflow = build_allocation_workflow(roster)

        return await run_workflow(workflow, payload)


def main() -> None:
    args = _parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
