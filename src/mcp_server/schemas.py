"""Pydantic models shared across the MCP server endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class DateRange(BaseModel):
    """Inclusive date interval used by the JSON datasets."""

    model_config = ConfigDict(json_encoders={date: lambda value: value.isoformat()})

    start_date: date = Field(description="Data inicial do intervalo.")
    end_date: date = Field(description="Data final do intervalo.")


class HealthStatus(BaseModel):
    """Simple health payload for readiness checks."""

    status: str = "ok"
    records: int


class StaffScheduleEntry(BaseModel):
    """Represents a scheduled employee assignment for a given day."""

    model_config = ConfigDict(json_encoders={date: lambda value: value.isoformat()})

    date: date
    employee_id: int
    name: str
    role: str
    shift: str
    status: str = Field(default="Active", description="Current staffing status (Active, Unavailable, etc.)")


class StaffScheduleSnapshot(BaseModel):
    """Serializable payload for the full schedule dataset."""

    model_config = ConfigDict(json_encoders={date: lambda value: value.isoformat()})

    date_range: DateRange
    staff_schedule: List[StaffScheduleEntry]


class StaffUpdate(BaseModel):
    """Represents an update affecting a scheduled employee."""

    model_config = ConfigDict(json_encoders={date: lambda value: value.isoformat(), datetime: lambda value: value.isoformat()})

    date: date
    employee_id: int
    name: str
    update_type: str
    details: str
    updated_by: str
    timestamp: datetime


class StaffUpdateSnapshot(BaseModel):
    """Serializable payload for staffing updates across the period."""

    model_config = ConfigDict(json_encoders={date: lambda value: value.isoformat(), datetime: lambda value: value.isoformat()})

    date_range: DateRange
    staff_updates: List[StaffUpdate]


class StaffingInsight(BaseModel):
    """Actionable recommendation derived from schedule and update data."""

    model_config = ConfigDict(json_encoders={date: lambda value: value.isoformat()})

    date: date
    shift: str
    role: str
    scheduled: int = Field(ge=0)
    available: int = Field(ge=0)
    delta: int
    risk_level: Literal["stable", "monitor", "critical"]
    recommendation: str


class WorkforceCoverageReport(BaseModel):
    """Aggregate view of staffing coverage along with metadata."""

    model_config = ConfigDict(json_encoders={date: lambda value: value.isoformat(), datetime: lambda value: value.isoformat()})

    generated_at: datetime
    date_range: DateRange
    insights: List[StaffingInsight]
    metadata: Dict[str, Optional[str]] = Field(default_factory=dict)


__all__ = [
    "DateRange",
    "HealthStatus",
    "StaffScheduleEntry",
    "StaffScheduleSnapshot",
    "StaffUpdate",
    "StaffUpdateSnapshot",
    "StaffingInsight",
    "WorkforceCoverageReport",
]
