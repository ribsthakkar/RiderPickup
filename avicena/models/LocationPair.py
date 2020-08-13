from haversine import haversine, Unit

from avicena.util.TimeWindows import ONE_MINUTE


class LocationPair:
    def __init__(self, l1, l2, speed):
        self.o = l1
        self.d = l2
        self.miles = haversine(self.o.coord, self.d.coord, Unit.MILES)
        self.time = (self.miles / float(speed)) / 24 + ONE_MINUTE
        if self.time > 1:
            print("Time Longer than a Day")
            print(self.o, self.o.coord)
            print(self.d, self.d.coord)
            print(self.miles, self.time, speed)
            exit(1)
