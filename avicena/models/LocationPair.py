import logging

from haversine import haversine, Unit

from avicena.models.Location import Location
from avicena.util.TimeWindows import ONE_MINUTE

log = logging.getLogger(__name__)


class LocationPair:
    """
    This class represents a pair of Location objects.
    It calculates the travel time between the locations based on a given speed
    as well as the distance in miles.
    """

    def __init__(self, l1: Location, l2: Location, speed: int) -> None:
        """
        Initialize a location pair object and compute the miles and travel time (in fraction of a day)
        :param l1: Origin Location of the Pair
        :param l2: Destination Location of the Pair
        :param speed: Assumed traveling speed between location in MPH
        """
        self.o = l1
        self.d = l2
        self.miles = haversine(self.o.coord, self.d.coord, Unit.MILES)
        self.time = (self.miles / float(speed)) / 24 + ONE_MINUTE
        if self.time > 1:
            log.warning(
                "Travel Time Longer than a Day for given speed. "
                f"origin:{self.o}, dest:{self.d}, miles:{self.miles}, "
                f"time:{self.time}, speed:{speed}")
