"""Utility hooks for workforce data processing."""
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Tuple

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


@lru_cache(maxsize=1)
def _get_staff_schedule() -> StaffScheduleSnapshot:
    if not STAFF_SCHEDULE_PATH.exists():
        raise FileNotFoundError(f"Staff schedule not found at {STAFF_SCHEDULE_PATH}")
    return StaffScheduleSnapshot.model_validate_json(STAFF_SCHEDULE_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _get_staff_updates() -> StaffUpdateSnapshot:
    if not STAFF_UPDATES_PATH.exists():
        raise FileNotFoundError(f"Staff updates not found at {STAFF_UPDATES_PATH}")
    return StaffUpdateSnapshot.model_validate_json(STAFF_UPDATES_PATH.read_text(encoding="utf-8"))


class WorkforceDataHook:
    """Facade around workforce datasets and derived analytics."""

    def get_schedule(self) -> StaffScheduleSnapshot:
        """Return the cached staffing schedule snapshot."""

        return _get_staff_schedule()

    def get_updates(self) -> StaffUpdateSnapshot:
        """Return the cached staffing updates snapshot."""

        return _get_staff_updates()

    def get_daily_staff(self, target_date: date) -> List[StaffScheduleEntry]:
        """Return employees scheduled to work on the requested date."""

        schedule = self.get_schedule()
        return [entry for entry in schedule.staff_schedule if entry.date == target_date]

    def get_daily_staff_updates(self, target_date: date) -> List[StaffUpdate]:
        """Return staffing updates recorded for the requested date."""

        updates_snapshot = self.get_updates()
        return [update for update in updates_snapshot.staff_updates if update.date == target_date]

    def coverage_report(
        self,
        date_filter: Optional[str] = None,
        role: Optional[str] = None,
        shift: Optional[str] = None,
    ) -> WorkforceCoverageReport:
        """Generate a workforce coverage report using schedule and update data."""

        schedule = self.get_schedule()
        updates = self.get_updates()
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

        parsed_date: Optional[date] = None
        if date_filter:
            try:
                parsed_date = datetime.fromisoformat(date_filter).date()
            except ValueError as exc:  # pragma: no cover - defensive validation
                raise ValueError(f"Invalid date filter '{date_filter}': {exc}") from exc

        filtered_insights = self._filter_insights(insights, parsed_date, role, shift)

        return WorkforceCoverageReport(
            generated_at=datetime.utcnow(),
            date_range=DateRange(
                start_date=schedule.date_range.start_date,
                end_date=schedule.date_range.end_date,
            ),
            insights=filtered_insights or insights,
            metadata={
                "filters.date": parsed_date.isoformat() if parsed_date else None,
                "filters.role": role,
                "filters.shift": shift,
                "total_insights": str(len(filtered_insights or insights)),
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


__all__ = ["WorkforceDataHook"]
