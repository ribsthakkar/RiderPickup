import datetime


def generate_html_label_for_addr(trips, addr):
    data = "<br>".join(
        "0" * (10 - len(str(t['trip_id']))) + str(t['trip_id']) + "  |  " + str(
            datetime.timedelta(days=float(t['est_pickup_time']))).split('.')[0] +
        "  |  " + str(t['driver_id']) for t in trips
    )
    return addr + "<br><b>TripID,             Time,      DriverID </b><br>" + data

def generate_html_label_for_driver_addr(d):
    return d.address[:-4] + "<br>Driver " + str(d.id) + " Home"

