"""Utility layer shared across the agent conversation demonstrations.

The module centralises logging, lightweight context manipulation helpers, and
instrumentation used to record execution metrics for each strategy. It also
exposes Semantic Kernel and Microsoft Agent Framework tools so agents can
persist shared context and query the Model Context Protocol server for
workforce optimisation insights.
"""
from __future__ import annotations

import logging
import os
import aiohttp
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Annotated, Any, Callable, Dict, Iterable, List, Mapping

from agent_framework import ai_function
from pydantic import Field
from semantic_kernel.functions import kernel_function

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)
WORKFORCE_BASE_URL_ENV = "WORKFORCE_MCP_BASE_URL"


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
LOGGER = logging.getLogger("agent_conversation")


def log_event(framework: str, agent: str, message: str, context: Dict[str, Any]) -> None:
    """Emit a structured log entry capturing the latest agent message."""

    LOGGER.info("[%s] %s: %s | context=%s", framework, agent, message, context)


def _merge_context(context: Dict[str, Any] | None, key: str, value: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(context or {})
    merged[key] = value
    return merged


def _require_env(var_name: str, fallback: str | None = None) -> str:
    value = os.getenv(var_name, fallback)
    if value:
        return value
    raise RuntimeError(f"Environment variable '{var_name}' must be defined to run this sample.")


def update_context(context: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
    """Return a shallow copy of *context* with *key* updated."""

    return _merge_context(context, key, value)


def ensure_env(var_name: str, fallback: str | None = None) -> str:
    """Return the environment variable value or raise a descriptive error."""

    return _require_env(var_name, fallback)


def to_plain_text(parts: Iterable[Any]) -> str:
    """Normalise message payloads returned by both frameworks to plain text."""

    buffer: List[str] = []
    for item in parts:
        text = getattr(item, "text", None)
        if text:
            buffer.append(text)
        elif isinstance(item, dict) and "text" in item:
            buffer.append(str(item["text"]))
        else:
            content_attr = getattr(item, "content", None)
            if isinstance(content_attr, str):
                buffer.append(content_attr)
    return "".join(buffer)


@dataclass(slots=True)
class OperationLog:
    """Capture a single timed operation executed by a conversation strategy."""

    framework: str
    phase: str
    action: str
    elapsed_ms: float
    timestamp: datetime
    metadata: Mapping[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        payload["metadata"] = dict(self.metadata)
        return payload


class OperationTracker:
    """Simple time-series tracker to record operations executed by a strategy."""

    def __init__(self) -> None:
        self._records: List[OperationLog] = []

    @property
    def records(self) -> List[OperationLog]:
        return list(self._records)

    @contextmanager
    def span(
        self,
        framework: str,
        phase: str,
        action: str,
        metadata_supplier: Callable[[], Mapping[str, Any]] | None = None,
    ):
        start = datetime.now(timezone.utc)
        start_perf = perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (perf_counter() - start_perf) * 1000
            metadata = metadata_supplier() if metadata_supplier else {}
            record = OperationLog(
                framework=framework,
                phase=phase,
                action=action,
                elapsed_ms=round(elapsed_ms, 2),
                timestamp=start,
                metadata=metadata,
            )
            self._records.append(record)
            LOGGER.info(
                "[%s] %s - %s | %.2f ms | metadata=%s",
                framework,
                phase,
                action,
                record.elapsed_ms,
                metadata,
            )

    def as_dict(self) -> List[Dict[str, Any]]:
        return [record.as_dict() for record in self._records]


def summarise_metrics(tracker: OperationTracker) -> List[Dict[str, Any]]:
    """Aggregate metrics per framework for logging and reporting."""

    grouped: Dict[str, Dict[str, float]] = {}
    for record in tracker.records:
        bucket = grouped.setdefault(record.framework, {"operations": 0.0, "elapsed": 0.0})
        bucket["operations"] += 1
        bucket["elapsed"] += record.elapsed_ms

    summary: List[Dict[str, Any]] = []
    for framework, metrics in grouped.items():
        operations = int(metrics["operations"])
        summary.append(
            {
                "framework": framework,
                "operations": operations,
                "total_ms": round(metrics["elapsed"], 2),
                "avg_ms": round(metrics["elapsed"] / operations if operations else 0.0, 2),
            }
        )
    return summary


def log_summary(tracker: OperationTracker) -> None:
    """Log a concise summary of all tracked operations."""

    for entry in summarise_metrics(tracker):
        LOGGER.info(
            "[Summary] %s | operations=%s | total_ms=%.2f | avg_ms=%.2f",
            entry["framework"],
            entry["operations"],
            entry["total_ms"],
            entry["avg_ms"],
        )


def _service_base_url() -> str:
    base_url = _require_env(WORKFORCE_BASE_URL_ENV)
    cleaned = base_url.rstrip("/")
    # The FastAPI routes are served at the root while the MCP bridge is mounted under /mcp.
    # Normalise configuration that points to the MCP mount to keep existing env files working.
    if cleaned.lower().endswith("/mcp"):
        cleaned = cleaned[: -len("/mcp")]
    return cleaned


def _build_url(path: str) -> str:
    return f"{_service_base_url()}/{path.lstrip('/')}"


async def _fetch_json(path: str, params: Dict[str, Any] | None = None) -> Any:
    url = _build_url(path)
    try:
        async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT) as session:
            async with session.get(url, params=params) as response:
                if response.status >= 400:
                    detail = await response.text()
                    raise RuntimeError(
                        f"Workforce MCP request to '{url}' failed with status {response.status}: {detail}"
                    )
                return await response.json()
    except aiohttp.ClientError as exc:
        raise RuntimeError(f"Workforce MCP request to '{url}' failed: {exc}") from exc


async def fetch_workforce_schedule() -> Dict[str, Any]:
    """Return the full staffing schedule snapshot from the MCP server."""

    return await _fetch_json("/workforce/schedule")


async def fetch_workforce_updates() -> Dict[str, Any]:
    """Return the full staffing updates snapshot from the MCP server."""

    return await _fetch_json("/workforce/updates")


async def fetch_daily_staff(target_date: str) -> List[Dict[str, Any]]:
    """Return the list of employees scheduled for the provided date (ISO format)."""

    return await _fetch_json("/workforce/daily-staff", params={"target_date": target_date})


async def fetch_daily_staff_updates(target_date: str) -> List[Dict[str, Any]]:
    """Return staffing updates recorded for the provided date (ISO format)."""

    return await _fetch_json("/workforce/daily-staff-updates", params={"target_date": target_date})


async def fetch_workforce_coverage(
    date_filter: str | None = None,
    role: str | None = None,
    shift: str | None = None,
) -> Dict[str, Any]:
    """Return the workforce coverage report for the supplied filters."""

    params: Dict[str, Any] = {}
    if date_filter:
        params["date_filter"] = date_filter
    if role:
        params["role"] = role
    if shift:
        params["shift"] = shift
    return await _fetch_json("/workforce/coverage", params=params or None)


class ConversationToolsPlugin:
    """Semantic Kernel plugin exposing shared conversation utilities and MCP tools."""

    @kernel_function(name="store_context", description="Update the shared context with a new key/value pair.")
    def store_context(self, context: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
        return _merge_context(context, key, value)

    @kernel_function(name="require_environment", description="Return the value of a required environment variable.")
    def require_environment(self, var_name: str, fallback: str | None = None) -> str:
        return _require_env(var_name, fallback)

    @kernel_function(
        name="get_staff_schedule",
        description="Retrieve the workforce schedule snapshot from the MCP service.",
    )
    async def get_staff_schedule(self) -> Dict[str, Any]:
        return await fetch_workforce_schedule()

    @kernel_function(
        name="get_staff_updates",
        description="Retrieve the workforce update snapshot from the MCP service.",
    )
    async def get_staff_updates(self) -> Dict[str, Any]:
        return await fetch_workforce_updates()

    @kernel_function(
        name="get_daily_staff",
        description="Retrieve the employees scheduled to work on a specific date (YYYY-MM-DD).",
    )
    async def get_daily_staff(self, target_date: str) -> List[Dict[str, Any]]:
        return await fetch_daily_staff(target_date)

    @kernel_function(
        name="get_daily_staff_updates",
        description="Retrieve staffing updates recorded on a specific date (YYYY-MM-DD).",
    )
    async def get_daily_staff_updates(self, target_date: str) -> List[Dict[str, Any]]:
        return await fetch_daily_staff_updates(target_date)

    @kernel_function(
        name="evaluate_workforce",
        description="Retrieve the workforce coverage report for the supplied filters.",
    )
    async def evaluate_workforce(
        self,
        date: str | None = None,
        role: str | None = None,
        shift: str | None = None,
    ) -> Dict[str, Any]:
        return await fetch_workforce_coverage(date_filter=date, role=role, shift=shift)


@ai_function(name="store_context", description="Update the shared context with the supplied value.")
def store_context_tool(
    context: Annotated[dict[str, Any], Field(description="Accumulated conversation context.")],
    key: Annotated[str, Field(description="Key to update in the shared context.")],
    value: Annotated[Any, Field(description="Value that will be associated with the key.")],
) -> dict[str, Any]:
    return _merge_context(context, key, value)


@ai_function(name="require_environment", description="Return the value of a required environment variable for the agent.")
def ensure_env_tool(
    var_name: Annotated[str, Field(description="Name of the environment variable.")],
    fallback: Annotated[str | None, Field(description="Optional value used when the variable is not set.")] = None,
) -> str:
    return _require_env(var_name, fallback)


@ai_function(
    name="get_staff_schedule",
    description="Retrieve the workforce schedule snapshot from the MCP service.",
)
async def get_staff_schedule_tool() -> Dict[str, Any]:
    return await fetch_workforce_schedule()


@ai_function(
    name="get_staff_updates",
    description="Retrieve the workforce update snapshot from the MCP service.",
)
async def get_staff_updates_tool() -> Dict[str, Any]:
    return await fetch_workforce_updates()


@ai_function(
    name="get_daily_staff",
    description="Retrieve the employees scheduled to work on a specific date (YYYY-MM-DD).",
)
async def get_daily_staff_tool(
    target_date: Annotated[str, Field(description="ISO date (YYYY-MM-DD) to retrieve staffing information for.")],
) -> list[dict[str, Any]]:
    return await fetch_daily_staff(target_date)


@ai_function(
    name="get_daily_staff_updates",
    description="Retrieve staffing updates recorded on a specific date (YYYY-MM-DD).",
)
async def get_daily_staff_updates_tool(
    target_date: Annotated[str, Field(description="ISO date (YYYY-MM-DD) to retrieve staffing updates for.")],
) -> list[dict[str, Any]]:
    return await fetch_daily_staff_updates(target_date)


@ai_function(
    name="evaluate_workforce",
    description="Retrieve the workforce coverage report for the supplied filters.",
)
async def evaluate_workforce_tool(
    date: Annotated[str | None, Field(description="Optional ISO date filter (YYYY-MM-DD).")] = None,
    role: Annotated[str | None, Field(description="Optional role filter.")] = None,
    shift: Annotated[str | None, Field(description="Optional shift filter.")] = None,
) -> dict[str, Any]:
    return await fetch_workforce_coverage(date_filter=date, role=role, shift=shift)


AGENT_FRAMEWORK_TOOLS = [
    store_context_tool,
    ensure_env_tool,
    get_staff_schedule_tool,
    get_staff_updates_tool,
    get_daily_staff_tool,
    get_daily_staff_updates_tool,
    evaluate_workforce_tool,
]

