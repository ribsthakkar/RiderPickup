import datetime

ONE_MINUTE = 0.00069444444

def get_time_window_by_hours_minutes(hours, minutes):
    return ONE_MINUTE * (60 * hours + minutes)

def fifteen_minutes():
    return get_time_window_by_hours_minutes(0, 15)

def timedelta_to_hhmmss(td):
    return str(td).split('.')[0]

def date_to_day_of_week(date):
    if date is None:
        day_of_week = datetime.datetime.now().timetuple().tm_wday
    else:
        m, d, y = date.split('-')
        day_of_week = datetime.datetime(int(y), int(m), int(d)).timetuple().tm_wday
    return day_of_week

def timedelta_to_fraction_of_day(td):
    return td.total_seconds() / (60 * 60 * 24)