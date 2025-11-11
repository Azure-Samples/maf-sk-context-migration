"""FastMCP server exposing workforce staffing insights."""
from __future__ import annotations

import contextlib
import json
import logging
from datetime import date
from typing import Any, Dict, Iterable, Optional

from starlette.applications import Starlette
from starlette.routing import Mount

import anyio
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ValidationError

from mcp_server.schemas import (
    StaffScheduleSnapshot,
    StaffUpdateSnapshot,
    WorkforceCoverageReport,
)
from mcp_server.utils import (
    CoverageReportStrategy,
    DailyStaffStrategy,
    DailyStaffUpdatesStrategy,
    ScheduleStrategy,
    UpdatesStrategy,
)

logger = logging.getLogger("mcp_server")


class _SuppressStreamableHttpNoise(logging.Filter):
    """Drop expected ClosedResourceError noise from stateless transports."""

    _SUPPRESSED_EXCEPTIONS = (anyio.ClosedResourceError, anyio.BrokenResourceError)

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        exc_type = record.exc_info[0] if record.exc_info else None
        if isinstance(exc_type, type) and issubclass(exc_type, self._SUPPRESSED_EXCEPTIONS):
            return False
        return True


logging.getLogger("mcp.server.streamable_http").addFilter(_SuppressStreamableHttpNoise())


class DailyStaffRequest(BaseModel):
    """Input payload for date-specific staffing queries."""

    date: Optional[date] = None


class CoverageReportRequest(BaseModel):
    """Optional filters when generating coverage insights."""

    date: Optional[date] = None
    role: Optional[str] = None
    shift: Optional[str] = None


def _dump_payload(payload: Any) -> Any:
    """Convert Pydantic models into JSON-serialisable structures."""

    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    if isinstance(payload, dict):
        return {key: _dump_payload(value) for key, value in payload.items()}
    if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
        return [_dump_payload(item) for item in payload]
    return payload


def _parse_payload(model: type[BaseModel], payload: Optional[Dict[str, Any]] = None) -> BaseModel:
    try:
        return model.model_validate(payload or {})
    except ValidationError as exc:
        details = ", ".join(err.get("msg", "Invalid field") for err in exc.errors()) if exc.errors() else "Invalid input payload."
        logger.warning("Validation error for %s: %s", model.__name__, details)
        raise ValueError(details) from exc


def _resolve_target_date(requested: Optional[date]) -> date:
    if requested is not None:
        return requested
    snapshot = ScheduleStrategy().execute()
    return snapshot.date_range.start_date


workforce_mcp = FastMCP(
    name="RetailIntelligenceMCP",
    instructions="Retail workforce staffing insights exposed via MCP tools.",
    json_response=True,
    stateless_http=True
)


LEGACY_METHOD_ALIASES: dict[str, tuple[str, Optional[Dict[str, Any]]]] = {
    "mcp.initialize": (
        "initialize",
        {
            "protocolVersion": "1.0",
            "clientInfo": {"name": "legacy-mcp-client", "version": "0.1"},
            "capabilities": {
                "roots": {"listChanged": False},
                "sampling": {},
            },
        },
    ),
    "mcp.ping": ("ping", {}),
    "mcp.list_tools": ("tools/list", {}),
    "mcp.call_tool": ("tools/call", None),
    "mcp.list_resources": ("resources/list", {}),
    "mcp.read_resource": ("resources/read", None),
    "mcp.subscribe_resource": ("resources/subscribe", None),
    "mcp.unsubscribe_resource": ("resources/unsubscribe", None),
    "mcp.list_resource_templates": ("resources/templates/list", {}),
    "mcp.list_prompts": ("prompts/list", {}),
    "mcp.get_prompt": ("prompts/get", None),
    "mcp.complete": ("completion/complete", None),
    "mcp.set_level": ("logging/setLevel", None),
}


class LegacyMCPShim:
    """Adapt older MCP method names emitted by some clients."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("method") == "POST" and scope.get("path", "") == "/mcp":
            body_chunks: list[bytes] = []
            more_body = True
            while more_body:
                message = await receive()
                body_chunks.append(message.get("body", b""))
                more_body = message.get("more_body", False)

            raw_body = b"".join(body_chunks)
            try:
                payload = json.loads(raw_body.decode() or "{}")
            except json.JSONDecodeError:
                payload = None

            if isinstance(payload, dict):
                method = payload.get("method")
                if isinstance(method, str) and method in LEGACY_METHOD_ALIASES:
                    alias, default_params = LEGACY_METHOD_ALIASES[method]
                    payload["method"] = alias
                    if default_params is not None:
                        existing_params = payload.get("params")
                        if not isinstance(existing_params, dict):
                            existing_params = {}
                        payload["params"] = {**default_params, **existing_params}
                    else:
                        payload.setdefault("params", {})
                elif isinstance(method, str) and method.startswith("mcp."):
                    payload.setdefault("params", {})

                raw_body = json.dumps(payload).encode()

            body_sent = False

            async def wrapped_receive():
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {"type": "http.request", "body": raw_body, "more_body": False}
                return {"type": "http.request", "body": b"", "more_body": False}

            await self.app(scope, wrapped_receive, send)
            return

        await self.app(scope, receive, send)


@workforce_mcp.tool(
    name="workforce.get_schedule",
    description="Return the complete staffing schedule snapshot, including the active date range."
)
async def get_schedule() -> Dict[str, Any]:
    snapshot: StaffScheduleSnapshot = ScheduleStrategy().execute()
    return _dump_payload(snapshot)


@workforce_mcp.tool(
    name="workforce.get_updates",
    description="Return the full set of staffing updates collected across the reporting window.",
)
async def get_updates() -> Dict[str, Any]:
    updates_snapshot: StaffUpdateSnapshot = UpdatesStrategy().execute()
    return _dump_payload(updates_snapshot)


@workforce_mcp.tool(
    name="workforce.get_daily_staff",
    description="Return all employees scheduled to work on the requested date.",
)
async def get_daily_staff(payload: Optional[DailyStaffRequest] = None) -> list[Dict[str, Any]]:
    request: DailyStaffRequest = _parse_payload(DailyStaffRequest, payload)  #type: ignore
    target_date = _resolve_target_date(request.date)
    try:
        entries = DailyStaffStrategy().execute(target_date=target_date)
    except LookupError as exc:
        raise ValueError(str(exc)) from exc
    return _dump_payload(entries)


@workforce_mcp.tool(
    name="workforce.get_daily_staff_updates",
    description="Return staffing updates recorded for a specific date.",
)
async def get_daily_staff_updates(payload: Optional[DailyStaffRequest] = None) -> list[Dict[str, Any]]:
    request: DailyStaffRequest = _parse_payload(DailyStaffRequest, payload)  #type: ignore
    target_date = _resolve_target_date(request.date)
    try:
        updates = DailyStaffUpdatesStrategy().execute(target_date=target_date)
    except LookupError as exc:
        raise ValueError(str(exc)) from exc
    return _dump_payload(updates)


@workforce_mcp.tool(
    name="workforce.get_coverage",
    description=(
        "Evaluate staffing coverage by merging the baseline schedule with workforce updates. "
        "Optional filters limit the insights to a specific date, role, or shift."
    )
)
async def get_coverage(payload: Optional[CoverageReportRequest] = None) -> Dict[str, Any]:
    request: CoverageReportRequest = _parse_payload(CoverageReportRequest, payload)  #type: ignore
    try:
        report: WorkforceCoverageReport = CoverageReportStrategy().execute(
            date_filter=request.date,
            role_filter=request.role,
            shift_filter=request.shift,
        )
    except LookupError as exc:
        raise ValueError(str(exc)) from exc
    return _dump_payload(report)


mcp_http_app = LegacyMCPShim(workforce_mcp.streamable_http_app())


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    async with workforce_mcp.session_manager.run():
        yield


app = Starlette(
    routes=[Mount("/", mcp_http_app)],
    lifespan=lifespan,
)


def main() -> None:
    import uvicorn
    uvicorn.run("mcp_server.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["workforce_mcp", "app", "main"]
