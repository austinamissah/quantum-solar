"""AMY-2018 calendar helpers: day-of-year -> month and weekday/weekend."""

import pytest

from quantum_solar.data import calendar as cal


# --- day_to_month ------------------------------------------------------------

def test_day_to_month_endpoints_and_july():
    assert cal.day_to_month(0) == 0        # Jan 1 -> January
    assert cal.day_to_month(364) == 11     # Dec 31 (non-leap) -> December
    # Jan..Jun = 31+28+31+30+31+30 = 181 days, so day index 181 is Jul 1.
    assert cal.day_to_month(181) == 6      # July (matches the summer URDB month)


def test_day_to_month_covers_all_twelve_months():
    months = {cal.day_to_month(d) for d in range(365)}
    assert months == set(range(12))


def test_day_out_of_range_rejected():
    for bad in (-1, 365, 366):
        with pytest.raises(ValueError, match="0-based day-of-year"):
            cal.day_to_month(bad)
        with pytest.raises(ValueError, match="0-based day-of-year"):
            cal.is_weekend(bad)


# --- weekday / weekend classification ----------------------------------------

def test_weekend_classification_against_known_2018_dates():
    # 2018-01-01 was a Monday.
    assert not cal.is_weekend(0)           # Mon Jan 1 -> weekday
    assert cal.is_weekend(5)               # Sat Jan 6 -> weekend
    assert cal.is_weekend(6)               # Sun Jan 7 -> weekend
    assert not cal.is_weekend(7)           # Mon Jan 8 -> weekday
    assert cal.day_type(0) == "weekday"
    assert cal.day_type(5) == "weekend"


def test_2018_has_104_weekend_days():
    # 2018 starts and ends on Monday: 52 Saturdays + 52 Sundays = 104 weekend days.
    weekend_days = sum(cal.is_weekend(d) for d in range(365))
    assert weekend_days == 104


def test_federal_holidays_are_rule_derived_not_hardcoded():
    """The 2018 federal set, including weekend-observed dates.

    Representative-day selection excludes these, so a wrong set silently puts an
    atypical day on a published figure.
    """
    import datetime

    from quantum_solar.data.calendar import AMY_YEAR, is_federal_holiday

    def doy(month, day):
        return (datetime.date(AMY_YEAR, month, day) - datetime.date(AMY_YEAR, 1, 1)).days

    expected = {
        (1, 1),    # New Year's Day
        (1, 15),   # MLK Day, 3rd Monday
        (2, 19),   # Washington's Birthday, 3rd Monday
        (5, 28),   # Memorial Day, last Monday
        (6, 19),   # Juneteenth (federal from 2021; included deliberately)
        (7, 4),    # Independence Day
        (9, 3),    # Labor Day, 1st Monday
        (10, 8),   # Columbus Day, 2nd Monday
        (11, 11),  # Veterans Day (a Sunday in 2018)
        (11, 12),  # ...and its observed Monday
        (11, 22),  # Thanksgiving, 4th Thursday
        (12, 25),  # Christmas
    }
    got = set()
    for day in range(365):
        if is_federal_holiday(day):
            date = datetime.date(AMY_YEAR, 1, 1) + datetime.timedelta(days=day)
            got.add((date.month, date.day))
    assert got == expected


def test_day_of_month_and_holidays_agree_with_day_type():
    """Holidays are still classified as weekdays: they are billed as such."""
    from quantum_solar.data.calendar import day_of_month, day_type, is_federal_holiday

    assert day_of_month(0) == 1
    assert day_of_month(364) == 31
    assert is_federal_holiday(0) and day_type(0) == "weekday"   # Mon 1 Jan
    assert is_federal_holiday(14) and day_type(14) == "weekday"  # MLK Day
    assert not is_federal_holiday(17)                            # Thu 18 Jan
