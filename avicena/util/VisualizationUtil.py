def generate_addr_label(trips, addr):
    data = "<br>".join(
        "0" * (10 - len(str(t['trip_id']))) + str(t['trip_id']) + "  |  " +
        str(timedelta(days=float(t['est_pickup_time']))).split('.')[0] +
        "  |  " + str(t['driver_id']) for t in trips
    )
    return addr + "<br><b>TripID,             Time,      DriverID </b><br>" + data

