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
