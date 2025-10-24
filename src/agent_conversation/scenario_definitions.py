"""Scenario definitions for agent conversations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class AgentFrameworkScenarioPrompts:
    facilitator_instructions: str
    expert_instructions: str
    kickoff_message: str
    expert_follow_up: str
    facilitator_wrap_up: str


@dataclass(frozen=True)
class SemanticKernelScenarioPrompts:
    researcher_instructions: str
    planner_instructions: str
    kickoff_message: str
    follow_up_prompt: str


@dataclass(frozen=True)
class ScenarioConfig:
    identifier: str
    title: str
    description: str
    target_date: str
    planning_horizon_days: int
    agent_framework: AgentFrameworkScenarioPrompts
    semantic_kernel: SemanticKernelScenarioPrompts


COVERAGE_ASSESSMENT: Final[ScenarioConfig] = ScenarioConfig(
    identifier="coverage_assessment",
    title="Coverage Assessment",
    description=(
        "Evaluate current store coverage and identify which employees should backfill"
        " uncovered shifts based on the workforce insights provided by the MCP service."
    ),
    target_date="2025-09-19",
    planning_horizon_days=1,
    agent_framework=AgentFrameworkScenarioPrompts(
        facilitator_instructions=(
            "You coordinate store operations. Review the coverage insights shared in the context"
            " and propose which employees should cover uncovered shifts while confirming with the specialist"
            " before finalising the plan."
        ),
        expert_instructions=(
            "You are the staffing specialist. Analyse the suggested allocations from the facilitator"
            " and provide concrete assignments for individuals to ensure full coverage."
        ),
        kickoff_message=(
            "We need to review today's staffing coverage report and assign backfills for any risk areas."
        ),
        expert_follow_up=(
            "Can you double-check the action items and ensure each uncovered shift has a named backup?"
        ),
        facilitator_wrap_up=(
            "Please confirm we can broadcast the coverage plan, including who is covering each critical shift."
        ),
    ),
    semantic_kernel=SemanticKernelScenarioPrompts(
        researcher_instructions=(
            "You are a technical researcher analysing staffing reports. Summarise the coverage issues"
            " and highlight which employees could backfill the riskier slots."
        ),
        planner_instructions=(
            "You are a planning agent. Build a short plan that maps specific employees to the highlighted"
            " coverage gaps, requesting confirmation at the end."
        ),
        kickoff_message=(
            "We are preparing for today's store operations. Review the coverage report and suggest"
            " how to fill the uncovered shifts with available employees."
        ),
        follow_up_prompt=(
            "Provide a concise briefing that we can share with the team once assignments are confirmed."
        ),
    ),
)


FUTURE_STAFFING: Final[ScenarioConfig] = ScenarioConfig(
    identifier="forward_staffing",
    title="Forward Staffing Plan",
    description=(
        "Draft a multi-day staffing plan that respects labour constraints (maximum 8 consecutive working"
        " hours, 5 consecutive days, and 10 hours per day) while balancing employee assignments using"
        " the information provided by the MCP datasets."
    ),
    target_date="2025-09-19",
    planning_horizon_days=3,
    agent_framework=AgentFrameworkScenarioPrompts(
        facilitator_instructions=(
            "You coordinate staffing for upcoming days. Use the shared schedule and updates to propose"
            " a rotation that honours labour constraints, then confirm decisions with the specialist."
        ),
        expert_instructions=(
            "You are the workforce specialist. Validate the facilitator's proposal, ensure hours and"
            " consecutive day limits are respected, and suggest adjustments when required."
        ),
        kickoff_message=(
            "We must draft the staffing rota for the next few days. Account for hour and day limits"
            " per employee while ensuring coverage."
        ),
        expert_follow_up=(
            "Please review the proposed rota and highlight any conflicts with the labour constraints."
        ),
        facilitator_wrap_up=(
            "Confirm that we can communicate the upcoming rota, noting any employees on watch for overtime risks."
        ),
    ),
    semantic_kernel=SemanticKernelScenarioPrompts(
        researcher_instructions=(
            "You analyse staffing data. Summarise availability for the next few days, considering"
            " labour constraints (max 8 consecutive hours, 5 consecutive days, 10 hours per day)."
        ),
        planner_instructions=(
            "You plan the rota. Build a staffing outline for the next few days honouring the constraints"
            " and request confirmation on any risky allocations."
        ),
        kickoff_message=(
            "We need a forward-looking staffing plan. Use the available data to recommend assignments"
            " for the next few days while respecting the labour constraints."
        ),
        follow_up_prompt=(
            "Summarise the proposed rota and flag any employees who might exceed the constraints."
        ),
    ),
)