"""FastAPI MCP server exposing workforce optimisation insights."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi_mcp import FastApiMCP

from .schemas import (
    HealthStatus,
    StaffScheduleEntry,
    StaffScheduleSnapshot,
    StaffUpdateSnapshot,
    StaffUpdate,
    WorkforceCoverageReport,
)
from .utils import WorkforceDataHook


hook = WorkforceDataHook()


app = FastAPI(
    title="Retail Workforce Intelligence Service",
    version="2.0.0",
    description="FastAPI application that surfaces workforce coverage insights as Model Context Protocol tools.",
)


@app.get("/health", response_model=HealthStatus, tags=["Diagnostics"], summary="Liveness / readiness probe")
async def health_check() -> HealthStatus:
    """Verify that the service can read the workforce schedule dataset."""

    schedule = hook.get_schedule()
    return HealthStatus(records=len(schedule.staff_schedule))


@app.get(
    "/workforce/schedule",
    response_model=StaffScheduleSnapshot,
    tags=["Workforce"],
    summary="Return the staffing schedule snapshot",
    operation_id="getstaffschedule",
)
async def workforce_schedule() -> StaffScheduleSnapshot:
    """Return the complete staffing schedule snapshot, including the active date range."""

    return hook.get_schedule()


@app.get(
    "/workforce/updates",
    response_model=StaffUpdateSnapshot,
    tags=["Workforce"],
    summary="Return the staffing updates snapshot",
    operation_id="getstaffupdates",
)
async def workforce_updates() -> StaffUpdateSnapshot:
    """Return the full set of staffing updates collected across the reporting window."""

    return hook.get_updates()


@app.get(
    "/workforce/daily-staff",
    response_model=List[StaffScheduleEntry],
    tags=["Workforce"],
    summary="Return the list of scheduled employees for a specific day",
    operation_id="getdailystaff",
)
async def daily_staff(
    target_date: date = Query(..., description="ISO date to retrieve staffing information for (YYYY-MM-DD)."),
) -> List[StaffScheduleEntry]:
    """Return all employees scheduled to work on the requested date."""

    entries = hook.get_daily_staff(target_date)
    if not entries:
        raise HTTPException(status_code=404, detail=f"No staffing records found for {target_date}.")
    return entries


@app.get(
    "/workforce/daily-staff-updates",
    response_model=List[StaffUpdate],
    tags=["Workforce"],
    summary="Return staffing updates recorded for a specific day",
    operation_id="getdailystaffupdates",
)
async def daily_staff_updates(
    target_date: date = Query(..., description="ISO date to retrieve staffing updates for (YYYY-MM-DD)."),
) -> List[StaffUpdate]:
    """Return every staffing update logged for the requested date."""

    updates = hook.get_daily_staff_updates(target_date)
    if not updates:
        raise HTTPException(status_code=404, detail=f"No staffing updates found for {target_date}.")
    return updates


@app.get(
    "/workforce/coverage",
    response_model=WorkforceCoverageReport,
    tags=["Workforce"],
    summary="Evaluate staffing coverage and provide optimisation suggestions",
    operation_id="getdailystaffcoverage",
)
async def workforce_coverage(
    date_filter: Optional[str] = Query(None, description="Optional ISO date filter (YYYY-MM-DD)."),
    role: Optional[str] = Query(None, description="Optional role filter."),
    shift: Optional[str] = Query(None, description="Optional shift filter."),
) -> WorkforceCoverageReport:
    """Return a coverage report that merges the baseline schedule with staffing updates."""

    try:
        report = hook.coverage_report(date_filter=date_filter, role=role, shift=shift)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not report.insights:
        raise HTTPException(status_code=404, detail="No staffing insights available for the supplied filters.")
    return report


mcp_bridge = FastApiMCP(
    fastapi=app,
    name="RetailIntelligenceMCP",
    description="Retail workforce staffing insights exposed via FastAPI and MCP tools.",
)
mcp_bridge.mount_http(mount_path="/mcp")


def _main() -> None:
    import uvicorn

    uvicorn.run("mcp-server.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":  # pragma: no cover
    _main()
