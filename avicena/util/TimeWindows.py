from datetime import datetime, timedelta
from typing import Optional

ONE_MINUTE = 0.00069444444


def get_time_window_by_hours_minutes(hours: int, minutes: int) -> float:
    """
    Get a fractional of a day representation given the hours and minutes
    :param hours: number of hours
    :param minutes: number of minutes
    :return: fraction of a day equivalent if the given hours and minutes passed from midnight
    """
    return ONE_MINUTE * (60 * hours + minutes)


def fifteen_minutes():
    """
    :return: Get a precalculated 15 minute fraction of day equivalent
    """
    return get_time_window_by_hours_minutes(0, 15)


def timedelta_to_hhmmss(td: timedelta) -> str:
    """
    Convert time delta object to a HH:MM:SS string
    :param td: input timedelta
    :return: HH:MM:SS rounded string of time delta
    """
    return str(td).split('.')[0]


def date_to_day_of_week(date: Optional[str] = None) -> int:
    """
    Convert a date into day of week
    :param date: Optional. If not passed in, then current day is used.
    :return: Day of the week starting with [0=Monday, 6=Sunday]
    """
    if date is None:
        day_of_week = datetime.now().timetuple().tm_wday
    else:
        m, d, y = date.split('-')
        day_of_week = datetime(int(y), int(m), int(d)).timetuple().tm_wday
    return day_of_week


def timedelta_to_fraction_of_day(td: timedelta) -> float:
    """
    Convert timedelta object to a fraction of a day completed representation
    :param td: timedelta object
    :return: fraction of day passed by timedelta
    """
    return td.total_seconds() / (60 * 60 * 24)