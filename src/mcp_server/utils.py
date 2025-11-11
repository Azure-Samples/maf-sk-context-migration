"""Strategies for workforce data processing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

from .schemas import (
    DateRange,
    StaffScheduleEntry,
    StaffScheduleSnapshot,
    StaffUpdate,
    StaffUpdateSnapshot,
    StaffingInsight,
    WorkforceCoverageReport,
)


STAFF_SCHEDULE_PATH = Path(__file__).with_name("daily_staff.json")
STAFF_UPDATES_PATH = Path(__file__).with_name("daily_updates.json")


def _load_schedule_snapshot() -> StaffScheduleSnapshot:
    if not STAFF_SCHEDULE_PATH.exists():
        raise FileNotFoundError(f"Staff schedule not found at {STAFF_SCHEDULE_PATH}")
    return StaffScheduleSnapshot.model_validate_json(STAFF_SCHEDULE_PATH.read_text(encoding="utf-8"))


def _load_updates_snapshot() -> StaffUpdateSnapshot:
    if not STAFF_UPDATES_PATH.exists():
        raise FileNotFoundError(f"Staff updates not found at {STAFF_UPDATES_PATH}")
    return StaffUpdateSnapshot.model_validate_json(STAFF_UPDATES_PATH.read_text(encoding="utf-8"))


class WorkforceStrategy(ABC):
    """Base strategy interface for workforce data operations."""

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Run the strategy and return a serialisable payload."""


class ScheduleStrategy(WorkforceStrategy):
    """Load the full staffing schedule snapshot."""

    def execute(self, **kwargs: Any) -> StaffScheduleSnapshot:  # noqa: ARG002 - strategies ignore kwargs
        return _load_schedule_snapshot()


class UpdatesStrategy(WorkforceStrategy):
    """Load the full staffing updates snapshot."""

    def execute(self, **kwargs: Any) -> StaffUpdateSnapshot:  # noqa: ARG002 - strategies ignore kwargs
        return _load_updates_snapshot()


class DailyStaffStrategy(WorkforceStrategy):
    """Retrieve scheduled employees for a specific date."""

    def execute(self, *, target_date: date, **_: Any) -> List[StaffScheduleEntry]:
        schedule = _load_schedule_snapshot()
        entries = [entry for entry in schedule.staff_schedule if entry.date == target_date]
        if not entries:
            raise LookupError(f"No staffing records found for {target_date.isoformat()}.")
        return entries


class DailyStaffUpdatesStrategy(WorkforceStrategy):
    """Retrieve staffing updates recorded for a specific date."""

    def execute(self, *, target_date: date, **_: Any) -> List[StaffUpdate]:
        updates_snapshot = _load_updates_snapshot()
        updates = [update for update in updates_snapshot.staff_updates if update.date == target_date]
        if not updates:
            raise LookupError(f"No staffing updates found for {target_date.isoformat()}.")
        return updates


class CoverageReportStrategy(WorkforceStrategy):
    """Generate a staffing coverage report based on schedule and updates."""

    def execute(
        self,
        *,
        date_filter: Optional[date] = None,
        role_filter: Optional[str] = None,
        shift_filter: Optional[str] = None,
        **_: Any,
    ) -> WorkforceCoverageReport:
        schedule = _load_schedule_snapshot()
        updates = _load_updates_snapshot()
        adjusted_entries = self._apply_staff_updates(schedule, updates)

        baseline = self._baseline_counts(schedule.staff_schedule)
        available = self._available_counts(adjusted_entries)

        insights: List[StaffingInsight] = []
        all_keys = set(baseline) | set(available)
        for key in sorted(all_keys):
            current_date, shift_name, role_name = key
            scheduled = baseline.get(key, 0)
            available_count = available.get(key, 0)
            delta = available_count - scheduled
            insights.append(
                StaffingInsight(
                    date=current_date,
                    shift=shift_name,
                    role=role_name,
                    scheduled=scheduled,
                    available=available_count,
                    delta=delta,
                    risk_level=self._risk_level(delta),
                    recommendation=self._recommendation(delta, role_name, shift_name),
                )
            )

        filtered_insights = self._filter_insights(insights, date_filter, role_filter, shift_filter)
        selected = filtered_insights or insights
        if not selected:
            raise LookupError("No staffing insights available for the supplied filters.")

        return WorkforceCoverageReport(
            generated_at=datetime.utcnow(),
            date_range=DateRange(
                start_date=schedule.date_range.start_date,
                end_date=schedule.date_range.end_date,
            ),
            insights=selected,
            metadata={
                "filters.date": date_filter.isoformat() if date_filter else None,
                "filters.role": role_filter,
                "filters.shift": shift_filter,
                "total_insights": str(len(selected)),
            },
        )

    @staticmethod
    def _normalize_key(entry: StaffScheduleEntry) -> Tuple[date, int]:
        return entry.date, entry.employee_id

    @staticmethod
    def _extract_shift_from_details(details: str) -> Optional[str]:
        lowered = details.lower()
        for marker in (" to ", " assigned to "):
            if marker in lowered:
                snippet = lowered.split(marker)[-1]
                return snippet.split(" due")[0].split(",")[0].strip().title()
        if "full day" in lowered:
            return "Full Day"
        return None

    @staticmethod
    def _extract_role_from_details(details: str) -> Optional[str]:
        lowered = details.lower()
        if "promoted to" in lowered:
            snippet = lowered.split("promoted to")[-1]
            return snippet.split(" due")[0].split(",")[0].strip().title()
        if "joined as" in lowered:
            snippet = lowered.split("joined as")[-1]
            return snippet.split(",")[0].strip().title()
        return None

    @classmethod
    def _apply_staff_updates(
        cls,
        schedule: StaffScheduleSnapshot,
        updates: StaffUpdateSnapshot,
    ) -> List[StaffScheduleEntry]:
        schedule_map: Dict[Tuple[date, int], StaffScheduleEntry] = {
            cls._normalize_key(entry): entry.model_copy(deep=True)
            for entry in schedule.staff_schedule
        }

        for update in updates.staff_updates:
            key = (update.date, update.employee_id)
            entry = schedule_map.get(key)
            if update.update_type.lower() == "new hire":
                role = cls._extract_role_from_details(update.details) or "Associate"
                shift = cls._extract_shift_from_details(update.details) or "Morning"
                schedule_map[key] = StaffScheduleEntry(
                    date=update.date,
                    employee_id=update.employee_id,
                    name=update.name,
                    role=role,
                    shift=shift,
                    status="Active",
                )
                continue
            if entry is None:
                continue
            lowered = update.update_type.lower()
            if "absence" in lowered:
                entry.status = "Unavailable"
            elif "shift change" in lowered:
                shift = cls._extract_shift_from_details(update.details)
                if shift:
                    entry.shift = shift
            elif "shift extension" in lowered:
                entry.shift = "Full Day"
            elif "role change" in lowered:
                role = cls._extract_role_from_details(update.details)
                if role:
                    entry.role = role
                else:
                    entry.status = "Transferred"

        return list(schedule_map.values())

    @staticmethod
    def _baseline_counts(entries: Iterable[StaffScheduleEntry]) -> Dict[Tuple[date, str, str], int]:
        counts: Dict[Tuple[date, str, str], int] = {}
        for entry in entries:
            key = (entry.date, entry.shift, entry.role)
            counts[key] = counts.get(key, 0) + 1
        return counts

    @staticmethod
    def _available_counts(entries: Iterable[StaffScheduleEntry]) -> Dict[Tuple[date, str, str], int]:
        counts: Dict[Tuple[date, str, str], int] = {}
        for entry in entries:
            if entry.status.lower() in {"unavailable", "transferred"}:
                continue
            key = (entry.date, entry.shift, entry.role)
            counts[key] = counts.get(key, 0) + 1
        return counts

    @staticmethod
    def _risk_level(delta: int) -> Literal["stable", "monitor", "critical"]:
        if delta >= 0:
            return "stable"
        if delta <= -2:
            return "critical"
        return "monitor"

    @staticmethod
    def _recommendation(delta: int, role: str, shift: str) -> str:
        if delta >= 0:
            return "Adequate coverage available for the requested shift."
        if delta == -1:
            return f"Consider reallocating staff to cover the {role} role during the {shift} shift."
        shortfall = abs(delta)
        return f"Add at least {shortfall} additional {role} team member(s) for the {shift} shift."

    @staticmethod
    def _filter_insights(
        insights: List[StaffingInsight],
        date_filter: Optional[date],
        role_filter: Optional[str],
        shift_filter: Optional[str],
    ) -> List[StaffingInsight]:
        role_norm = role_filter.lower() if role_filter else None
        shift_norm = shift_filter.lower() if shift_filter else None
        filtered: List[StaffingInsight] = []
        for insight in insights:
            if date_filter and insight.date != date_filter:
                continue
            if role_norm and insight.role.lower() != role_norm:
                continue
            if shift_norm and insight.shift.lower() != shift_norm:
                continue
            filtered.append(insight)
        return filtered


__all__ = [
    "WorkforceStrategy",
    "ScheduleStrategy",
    "UpdatesStrategy",
    "DailyStaffStrategy",
    "DailyStaffUpdatesStrategy",
    "CoverageReportStrategy",
]
