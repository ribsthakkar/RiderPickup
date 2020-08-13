from avicena.models.Location import Location
from avicena.models.LocationPair import LocationPair
from avicena.util.Exceptions import InvalidTripException
from avicena.util.Geolocator import find_coord_lat_lon
from avicena.util.ParserUtil import convert_time
from avicena.util.TimeWindows import get_time_window_by_hours_minutes


class Trip:
    def __init__(self, pickup: Location, dropoff: Location, space, trip_id, scheduled_pickup, scheduled_dropoff, speed, is_merge, revenue=0.0, preset_miles=0, lp=None):
        self.id = trip_id
        if lp:
            self.lp = lp
        else:
            self.lp = LocationPair(pickup, dropoff, speed)
        self.space = space
        self.scheduled_pickup = max(0.0, scheduled_pickup)
        self.scheduled_dropoff = 1.0 if scheduled_dropoff == 0 else scheduled_dropoff
        self.required_level_of_service = 'W' if space == 1.5 else 'A'
        self.is_merge = is_merge
        self.rev = revenue
        if self.lp.time > scheduled_dropoff - max(0, scheduled_pickup - get_time_window_by_hours_minutes(0, 20)):
            raise InvalidTripException("Trip ID:" + str(id) + " start:" + str(scheduled_pickup) + " end:" + str(scheduled_dropoff) + " trip length: " + str(self.lp.time))
        self.preset_miles = preset_miles

    def __repr__(self):
        return repr(self.lp.o) + "->" + repr(self.lp.d)


def load_trips_from_df(trip_df, speed):
    trips = []
    for _, row in trip_df.iterrows():
        pickup_coord = (row['trip_pickup_lat'], row['trip_pickup_lon'])
        dropoff_coord = (row['trip_dropoff_lat'], row['trip_dropoff_lon'])
        pickup = Location(row['trip_pickup_address'] + "P" + str(hash(row['trip_id']))[:3], pickup_coord, suffix_len=4)
        dropoff = Location(row['trip_dropoff_address'] + "D" + str(hash(row['trip_id']))[:3], dropoff_coord, suffix_len=4)
        scheduled_pickup = convert_time(str(row['trip_pickup_time']))
        scheduled_dropoff = convert_time(str(row['trip_dropoff_time']))
        capacity_needed = 1 if row['trip_los'] == 'A' else 1.5
        id = row['trip_id']
        rev = float(row['trip_revenue'])
        trips.append(Trip(pickup, dropoff, capacity_needed, id, scheduled_pickup, scheduled_dropoff, speed, row['merge_flag'], rev, preset_miles=int(row['trip_miles'])))
    return trips
