from typing import Optional, Union, List

from pandas import DataFrame

from avicena.models.Location import Location
from avicena.models.LocationPair import LocationPair
from avicena.util.Exceptions import InvalidTripException
from avicena.util.ParserUtil import convert_time
from avicena.util.TimeWindows import get_time_window_by_hours_minutes


class Trip:
    """
    This class represents an instance of a trip, which is a Location pair with some shceduled pickup, dropoff, revenue, and space required
    These Trip objects are generated from the parsed Trips from the model input and during the Optimizer's run time in order
    to represent other combinations of places a driver can travel.
    """

    def __init__(self, pickup: Location, dropoff: Location, space: float, trip_id: Union[str, int],
                 scheduled_pickup: float, scheduled_dropoff: float, speed: int, is_merge: bool, revenue: float = 0.0,
                 preset_miles: int = 0, lp: Optional[LocationPair] = None):
        """
        Initialize a Trip
        :param pickup: Pickup Location
        :param dropoff: Dropoff Location
        :param space: Space required for the trip
        :param trip_id: An unique identifier for the trip. They are strings when parsed from the input but can be integers when models generate them.
        :param scheduled_pickup: The scheduled pickup time represented as a fraction of the day passed (i.e. 16:00 = 4:00pm = 0.666)
        :param scheduled_dropoff: The scheduled dropoff time represented as a fraction of the day passed (i.e. 16:00 = 4:00pm = 0.666)
        :param speed: Estimated traveling speed when completing trip
        :param is_merge: Indicator of whether this is a merge trip
        :param revenue: (optional; default = 0) Revenue earned for completing this trip
        :param preset_miles: (optional; default = 0) Fixed number of miles provided by the input set of trips with which the revenue is calculated
        :param lp: (optional) Use an already prepared location pair instead of instantiating a new one
        """
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
            raise InvalidTripException("Trip ID:" + str(id) + " start:" + str(scheduled_pickup) + " end:" + str(
                scheduled_dropoff) + " trip length: " + str(self.lp.time))
        self.preset_miles = preset_miles

    def __repr__(self) -> str:
        """
        :return: String representation of where the trip begins and ends
        """
        return repr(self.lp.o) + "->" + repr(self.lp.d)


def load_and_filter_valid_trips_from_df(trip_df: DataFrame, speed: int) -> List[Trip]:
    """
    Filter out the invalid trips in the data frame and generate a list of Trip objects.
    For any invalid trips, all other legs of the trip associated with an invalid leg are also marked invalid and
    filtered away. This function assumes the IDs of a patient's trip legs end in 'A' , 'B' , or 'C'.
    :param trip_df: Input dataframe of parsed/prepared trip data
    :param speed: Assumed speed for all trips
    :return: List of valid Trip objects. All invalid trips and their legs are ignored.
    """
    trips = []
    ignore_ids = set()
    for _, row in trip_df.iterrows():
        pickup_coord = (row['trip_pickup_lat'], row['trip_pickup_lon'])
        dropoff_coord = (row['trip_dropoff_lat'], row['trip_dropoff_lon'])
        pickup = Location(row['trip_pickup_address'] + "P" + str(hash(row['trip_id']))[:3], pickup_coord, suffix_len=4)
        dropoff = Location(row['trip_dropoff_address'] + "D" + str(hash(row['trip_id']))[:3], dropoff_coord,
                           suffix_len=4)
        scheduled_pickup = convert_time(str(row['trip_pickup_time']))
        scheduled_dropoff = convert_time(str(row['trip_dropoff_time']))
        capacity_needed = 1 if row['trip_los'] == 'A' else 1.5
        id = row['trip_id']
        rev = float(row['trip_revenue'])
        try:
            trips.append(Trip(pickup, dropoff, capacity_needed, id, scheduled_pickup, scheduled_dropoff, speed,
                              row['merge_flag'], rev, preset_miles=int(row['trip_miles'])))
        except InvalidTripException:
            ignore_ids.add(id[:-1] + 'A')
            ignore_ids.add(id[:-1] + 'B')
            ignore_ids.add(id[:-1] + 'C')
    return list(filter(lambda t: t.id not in ignore_ids, trips))
