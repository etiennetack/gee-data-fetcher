# -*- coding: utf-8 -*-
from typing import Generator

import pendulum

__all__ = [
    "iter_periods",
    "parse_period",
    "parse_period_unit",
]


def iter_periods(
    start: str,
    end: str,
    period_size: str,
    period_frequency: str,
) -> Generator[pendulum.Interval, None, None]:
    """Generate periodic intervals between start and end dates. Also parse date
    strings and period arguments (size and frequency)."""

    start = pendulum.parse(start)

    if end == "now":
        end = pendulum.now()
    else:
        end = pendulum.parse(end)

    period_size, period_unit = parse_period(period_size)

    if period_frequency is not None:
        period_frequency, period_frequency_unit = parse_period(period_frequency)
    else:
        # If period_frequency is not provided, then use period_size as period_frequency
        period_frequency, period_frequency_unit = period_size, period_unit

    return (
        # Get period end date by adding the period size and subtracting 1 day
        (
            (
                period_start
                + pendulum.duration(**{period_unit: period_size})
                - pendulum.duration(days=1)
            )
            # go to the end of the day (i.e., 23:59:59.999999)
            .end_of("day")
        )
        # Construct new period interval
        - period_start
        # Iterate over the period start dates
        for period_start in pendulum.interval(start, end).range(
            period_frequency_unit, period_frequency
        )
    )


def parse_period(period_size: str) -> (int, str):
    """Parse the period size and unit."""
    if len(period_size) < 2:
        if period_size[-1].isdigit():
            raise ValueError(
                f"Invalid period size format ({period_size[-1]} does not represent a valid period unit)."
            )

    period_unit = parse_period_unit(period_size[-1].lower())

    if len(period_size) == 1:
        period_size = 1
    elif period_size[:-1].isdigit():
        period_size = int(period_size[:-1])
    else:
        raise ValueError(
            f"Invalid period size format ({period_size[:-1]} is not a number)."
        )

    return period_size, period_unit


def parse_period_unit(period_unit: str) -> str:
    """Parse the period unit (small representation to full)."""
    if period_unit == "d":
        return "days"
    elif period_unit == "w":
        return "weeks"
    elif period_unit == "m":
        return "months"
    elif period_unit == "y":
        return "years"
    else:
        raise ValueError(f"Invalid period unit: {period_unit}")
