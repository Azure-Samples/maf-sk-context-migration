"""Scenario strategies orchestrating framework conversations."""
from __future__ import annotations

from random import choice
from time import perf_counter
from typing import Iterable, List

from .maf import run_agent_framework_conversation
from .scenario_definitions import COVERAGE_ASSESSMENT, FUTURE_STAFFING, ScenarioConfig
from .sk import run_semantic_kernel_conversation
from .strategy import ConversationStrategy, ScenarioResult
from .tools import LOGGER


class ScenarioConversationStrategy(ConversationStrategy):
    """Base strategy executing both frameworks for a given scenario."""

    def __init__(self, config: ScenarioConfig) -> None:
        self._config = config
        self.identifier = config.identifier
        self.title = config.title
        self.description = config.description

    async def execute(self) -> ScenarioResult:
        runners = [
            run_semantic_kernel_conversation,
            run_agent_framework_conversation,
        ]
        conversations = []
        for index, runner in enumerate(runners, start=1):
            LOGGER.info(
                "[Scenario] %s | step=%s | framework=%s | status=starting",
                self.identifier,
                index,
                runner.__name__,
            )
            start = perf_counter()
            conversation = await runner(self._config)
            elapsed_ms = (perf_counter() - start) * 1000
            conversations.append(conversation)
            LOGGER.info(
                "[Scenario] %s | step=%s | framework=%s | status=completed | elapsed_ms=%.2f",
                self.identifier,
                index,
                conversation.framework,
                elapsed_ms,
            )
        return ScenarioResult(
            identifier=self.identifier,
            title=self.title,
            description=self.description,
            conversations=conversations,
        )


class CoverageAssessmentScenarioStrategy(ScenarioConversationStrategy):
    """Scenario focused on resolving immediate coverage gaps."""

    def __init__(self) -> None:
        super().__init__(COVERAGE_ASSESSMENT)


class ForwardStaffingScenarioStrategy(ScenarioConversationStrategy):
    """Scenario focused on planning future staffing rotations."""

    def __init__(self) -> None:
        super().__init__(FUTURE_STAFFING)


def available_strategies() -> List[ConversationStrategy]:
    return [CoverageAssessmentScenarioStrategy(), ForwardStaffingScenarioStrategy()]


def select_strategies(selection: str | None = None) -> Iterable[ConversationStrategy]:
    strategies = available_strategies()
    if not selection or selection.lower() == "random":
        return [choice(strategies)]

    selection_lower = selection.lower()
    if selection_lower in {"coverage", COVERAGE_ASSESSMENT.identifier}:
        return [CoverageAssessmentScenarioStrategy()]
    if selection_lower in {"forward", FUTURE_STAFFING.identifier}:
        return [ForwardStaffingScenarioStrategy()]

    return strategies
