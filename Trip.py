from enum import Enum
import requests
from opencage.geocoder import OpenCageGeocode
from time import sleep
from haversine import haversine, Unit
from geopy.geocoders import Nominatim
from constants import *

try:
    from locations import locations_cache
    locations = locations_cache # cached dict mapping an address to its lat long, not in repository for privacy
except:
    locations = dict()
    pass

class TripType(Enum):
    A = 1 # Destination is a home without passenger Must be before B for a location
    B = 2 # Destination is a hospital with passenger Must be before C for a location
    C = 3 # Destination is a hospital without a passenger Must be before D for a location
    D = 4 # Destination is a home with a passenger
    INTER_A = 5 # From driver home to any other location Must occur before any A trips
    INTER_B = 6 # From any location to driver home Must occur after all D trips
    MERGE = 7
class InvalidTripException(Exception):
    pass
class Trip:
    def __init__(self, o, d, space, id, type, start, end, rev= 0, preset_miles = 0, lp = None, prefix=False, suffix=False, prefixLen=3, suffixLen=4):
        self.type = type
        self.id = id
        if lp:
            self.lp = lp
        else:
            self.lp = LocationPair(o, d, prefix=prefix, suffix=suffix, plen=prefixLen, slen=suffixLen)
        self.space = space
        self.start = max(0.0, start)
        self.end = 1.0 if end == 0 else end
        self.los = 'W' if space == 1.5 else 'A'
        self.rev = rev
        if self.lp.time > end - max(0, start - BUFFER):
            raise InvalidTripException()
        self.preset_m = preset_miles
    def __repr__(self):
        return self.lp.o + "->" + self.lp.d

class Location:
    def __init__(self, addr, coord = None):
        self.addr = addr
        if coord is None and self.addr in locations:
            self.coord = locations[self.addr]
        elif coord is None:
            loc1 = self.find_coord(addr)
            locations[self.addr] = loc1
            self.coord = locations[self.addr]
        else:
            self.coord = coord

    def find_coord(self, addr):
        geo_api = "78bdef6c2b254abaa78c55640925d3db"
        # geo_api = "3c8dd43d76194d28bf62f76a46b305c4"
        geolocator = OpenCageGeocode(geo_api)
        l1loc = geolocator.geocode(addr)
        return (l1loc[0]['geometry']['lat'], l1loc[0]['geometry']['lng'])

    def rev_coord(self):
        return tuple(reversed(self.coord))

class LocationPair:
    def __init__(self, l1, l2, c1=None, c2=None, prefix=False, suffix=False, plen=3, slen=4):
        self.o = l1
        self.d = l2
        if c1:
            self.c1 = c1
        else:
            if prefix:
                l1 = l1[plen:]
            if suffix:
                l1 = l1[:-slen]
            self.c1 = self.getCoords(l1)

        if c2:
            self.c2 = c2
        else:
            if prefix:
                l2 = l2[plen:]
            if suffix:
                l2 = l2[:-slen]
            self.c2 = self.getCoords(l2)

        self.miles = haversine(self.c1, self.c2, Unit.MILES)
        speed = self.get_speed(self.miles)
        self.time = (self.miles / speed) / 24
        if self.time > 1:
            print(self.miles, self.time, speed)
            exit(1)

    def getCoords(self, l1):
        return Location(l1).coord

    def get_speed(self, miles):
        return 60       # Adjust speed if needed
        # if miles < 30:
        #     # print(50)
        #     return 50
        # if miles < 50:
        #     # print(60)
        #     return 60
        # else:
        #     # print(70)
        #     return 70

