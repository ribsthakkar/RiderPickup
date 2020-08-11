ONE_MINUTE = 0.00069444444

def get_time_window_by_hours_minutes(hours, minutes):
    return ONE_MINUTE * (60 * hours + minutes)

def fifteen_minutes():
    return get_time_window_by_hours_minutes(0, 15)