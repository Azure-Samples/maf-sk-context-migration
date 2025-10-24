"""Strategy abstractions for agent conversation demonstrations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(slots=True)
class FrameworkConversationResult:
    """Structured representation of a single framework conversation."""

    framework: str
    transcript: List[Dict[str, Any]]
    context_snapshot: Dict[str, Any]
    metrics: List[Dict[str, Any]]

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation of the conversation."""

        return {
            "framework": self.framework,
            "transcript": list(self.transcript),
            "context": dict(self.context_snapshot),
            "metrics": list(self.metrics),
        }


@dataclass(slots=True)
class ScenarioResult:
    """Aggregated result capturing the outcome of a scenario across frameworks."""

    identifier: str
    title: str
    description: str
    conversations: List[FrameworkConversationResult]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scenario": {
                "identifier": self.identifier,
                "title": self.title,
                "description": self.description,
            },
            "conversations": [conversation.as_dict() for conversation in self.conversations],
        }


class ConversationStrategy(ABC):
    """Contract implemented by all scenario strategies."""

    identifier: str
    title: str
    description: str

    @abstractmethod
    async def execute(self) -> ScenarioResult:
        """Run the scenario and return aggregated framework conversations."""
