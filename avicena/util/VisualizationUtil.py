import datetime

from pandas import Series

from avicena.models.Driver import Driver


def generate_html_label_for_addr(trips: Series, addr: str) -> str:
    """
    Generate specialized string label with HTML tags of trips passing by a specific address
    :param trips: Trips passing by address
    :param addr: Original address of location
    :return: HTML Formatted details about trips going through specified address
    """
    data = "<br>".join(
        "0" * (10 - len(str(t['trip_id']))) + str(t['trip_id']) + "  |  " + str(
            datetime.timedelta(days=float(t['est_pickup_time']))).split('.')[0] +
        "  |  " + str(t['driver_id']) for t in trips
    )
    return addr + "<br><b>TripID,             Time,      DriverID </b><br>" + data


def generate_html_label_for_driver_addr(d: Driver) -> str:
    """
    Generate a driver HTML Label for visualization
    :param d: Driver object
    :return: HTML formatted driver address
    """
    return d.get_clean_address() + "<br>Driver " + str(d.id) + " Home"
