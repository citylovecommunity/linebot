"""
Next-run display helper for the admin dashboard.

The actual cron schedules live in GCP Cloud Scheduler (not versioned in this
repo — see CLAUDE.md). These constants must be kept in sync by hand whenever
the schedule is changed in the GCP console.

As of the current GCP config (`gcloud scheduler jobs list`):
  group-match      0 8 * * 4  (Asia/Taipei)  ?week_gate=even
  Weekly_Matching  0 8 * * 4  (Asia/Taipei)  ?week_gate=odd
  stale-draft      0 20 * * * (Asia/Taipei)

Both matching jobs fire every Thursday at 08:00, but `week_gate` (handled in
routes/tasks.py via `date.today().isocalendar()[1] % 2`) makes only one of
them actually run on any given Thursday — they alternate by ISO week parity.
stale-draft runs every day at 20:00 with no gating.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

THURSDAY = 3  # datetime.weekday(): Monday=0 ... Sunday=6

GROUP_MATCH_SCHEDULE = (THURSDAY, 8, 0, 'even')       # cron: 0 8 * * 4, ?week_gate=even
ONE_TO_ONE_MATCH_SCHEDULE = (THURSDAY, 8, 0, 'odd')   # cron: 0 8 * * 4, ?week_gate=odd

STALE_DRAFT_SCHEDULE = (20, 0)  # cron: 0 20 * * *


def next_occurrence(weekday: int, hour: int, minute: int, parity: str, now: datetime | None = None) -> datetime:
    """Return the next datetime the gated weekly job actually runs.

    `weekday` follows datetime.weekday() (Monday=0); `parity` is 'even' or
    'odd', matched against the target date's ISO week number.
    """
    now = now or datetime.now()
    days_ahead = (weekday - now.weekday()) % 7
    candidate = datetime.combine(now.date() + timedelta(days=days_ahead), time(hour, minute))
    if candidate <= now:
        candidate += timedelta(days=7)

    want_even = parity == 'even'
    while (candidate.isocalendar()[1] % 2 == 0) != want_even:
        candidate += timedelta(days=7)
    return candidate


def next_daily_occurrence(hour: int, minute: int, now: datetime | None = None) -> datetime:
    """Return the next datetime an un-gated daily job runs at hour:minute."""
    now = now or datetime.now()
    candidate = datetime.combine(now.date(), time(hour, minute))
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate
