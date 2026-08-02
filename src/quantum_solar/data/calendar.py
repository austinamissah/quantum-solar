"""AMY-2018 calendar helpers for the annual loop.

The packaged load profiles (see :mod:`load_profile` and ``profiles/SOURCE.md``)
are derived from NREL ResStock's ``resstock_amy2018_release_2`` run, which
averages — for example — the 22 July *weekdays* exactly as the 2018 calendar
defines them. So classifying a day-of-year as weekday vs weekend MUST use 2018;
any other year would apply weekday load profiles to days the source data treated
as weekends (and vice versa).

2018 is pinned for that provenance reason and because it is **non-leap**: a
``range(365)`` annual loop aligns 1:1 with the 8760-hour PVWatts array with no
Feb-29 case to special-case. Do not make the year dynamic — a leap year would
desync the day index from the 8760-hour grid.
"""

from __future__ import annotations

import datetime

# Non-leap; see module docstring. Not a parameter — do not change.
AMY_YEAR = 2018

_JAN1 = datetime.date(AMY_YEAR, 1, 1)


def _date(day: int) -> datetime.date:
    if not 0 <= day <= 364:
        raise ValueError(f"day must be a 0-based day-of-year in 0..364 (non-leap {AMY_YEAR}), got {day}")
    return _JAN1 + datetime.timedelta(days=day)


def day_to_month(day: int) -> int:
    """0-based day-of-year (0..364) -> 0-based month (0=Jan .. 11=Dec), AMY 2018.

    0-based to index URDB's 12-month ``energy*schedule`` arrays directly.
    """
    return _date(day).month - 1


def is_weekend(day: int) -> bool:
    """True if the 0-based day-of-year falls on Sat/Sun in AMY 2018.

    US federal holidays are NOT treated as weekends: URDB carries no holiday
    schedule and the ResStock weekday aggregate folds holidays into weekdays, so
    both price and load bill holidays as ordinary weekdays here — a known v1
    limitation (see :func:`quantum_solar.data.nrel.fetch_urdb_tou`).
    """
    return _date(day).weekday() >= 5  # Mon=0 .. Sat=5, Sun=6


def day_type(day: int) -> str:
    """``"weekend"`` or ``"weekday"`` for a 0-based day-of-year in AMY 2018.

    The load-profile key axis (with ``day_to_month``): ``load_profile(month, day_type)``.
    """
    return "weekend" if is_weekend(day) else "weekday"
