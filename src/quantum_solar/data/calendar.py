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


def day_of_month(day: int) -> int:
    """0-based day-of-year (0..364) -> 1-based day of its month, AMY 2018."""
    return _date(day).day


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


def _nth_weekday(month: int, weekday: int, n: int) -> datetime.date:
    """``n``-th ``weekday`` (Mon=0) of ``month`` in AMY 2018; ``n=-1`` means the last."""
    first = datetime.date(AMY_YEAR, month, 1)
    if n == -1:
        nxt = datetime.date(AMY_YEAR, month + 1, 1) if month < 12 else datetime.date(AMY_YEAR + 1, 1, 1)
        last = nxt - datetime.timedelta(days=1)
        return last - datetime.timedelta(days=(last.weekday() - weekday) % 7)
    offset = (weekday - first.weekday()) % 7
    return first + datetime.timedelta(days=offset + 7 * (n - 1))


def _federal_holidays() -> frozenset[datetime.date]:
    """US federal holidays in AMY 2018, plus their weekend-observed dates.

    Rule-based rather than a date list so the set cannot silently rot, and
    deliberately includes Juneteenth, which only became federal in 2021: this set
    is used to *exclude* days from representative-day selection, so over-inclusion
    is the safe direction.
    """
    fixed = [(1, 1), (6, 19), (7, 4), (11, 11), (12, 25)]
    days = {datetime.date(AMY_YEAR, m, d) for m, d in fixed}
    days |= {
        _nth_weekday(1, 0, 3),    # MLK Day: 3rd Monday of January
        _nth_weekday(2, 0, 3),    # Washington's Birthday: 3rd Monday of February
        _nth_weekday(5, 0, -1),   # Memorial Day: last Monday of May
        _nth_weekday(9, 0, 1),    # Labor Day: 1st Monday of September
        _nth_weekday(10, 0, 2),   # Columbus Day: 2nd Monday of October
        _nth_weekday(11, 3, 4),   # Thanksgiving: 4th Thursday of November
    }
    observed = set()
    for d in days:  # Sat -> observed Friday, Sun -> observed Monday
        if d.weekday() == 5:
            observed.add(d - datetime.timedelta(days=1))
        elif d.weekday() == 6:
            observed.add(d + datetime.timedelta(days=1))
    return frozenset(days | observed)


_FEDERAL_HOLIDAYS = _federal_holidays()


def is_federal_holiday(day: int) -> bool:
    """True if the 0-based day-of-year is a US federal holiday (or observance) in AMY 2018.

    This does **not** change how a day is billed: :func:`is_weekend` still treats
    holidays as ordinary weekdays, because URDB carries no holiday schedule and
    the ResStock weekday aggregate folds holidays in. That limitation is exactly
    why this helper exists — it lets *representative-day selection* avoid the days
    where the limitation is most conspicuous, without pretending to model them.
    """
    return _date(day) in _FEDERAL_HOLIDAYS
