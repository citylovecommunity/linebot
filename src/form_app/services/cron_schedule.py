"""
Next-run display helper for the admin dashboard.

The actual cron schedules live in GCP Cloud Scheduler (not versioned in this
repo — see CLAUDE.md). These constants must be kept in sync by hand whenever
the schedule is changed in the GCP console.
"""
from __future__ import annotations

from datetime import datetime

# (days of month, hour, minute) — 24h clock, matches GCP Scheduler's cron field order.
GROUP_MATCH_SCHEDULE = ([9, 23], 8, 0)          # cron: 0 8 9,23 * *
ONE_TO_ONE_MATCH_SCHEDULE = ([16, 30], 8, 0)    # cron: 0 8 16,30 * *

# Stale-draft auto-send fires 12h after either matching job, on all 4 days.
STALE_DRAFT_SCHEDULE = ([9, 16, 23, 30], 20, 0)  # cron: 0 20 9,16,23,30 * *


def next_occurrence(days_of_month: list[int], hour: int, minute: int, now: datetime | None = None) -> datetime:
    """Return the next datetime matching one of the given days-of-month at hour:minute."""
    now = now or datetime.now()
    candidates = []
    for month_offset in (0, 1, 2):
        year = now.year + (now.month - 1 + month_offset) // 12
        month = (now.month - 1 + month_offset) % 12 + 1
        for day in days_of_month:
            try:
                candidate = datetime(year, month, day, hour, minute)
            except ValueError:
                continue  # e.g. day 30 in February
            if candidate > now:
                candidates.append(candidate)
    return min(candidates)
