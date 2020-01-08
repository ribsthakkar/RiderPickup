from enum import Enum
import requests
from opencage.geocoder import OpenCageGeocode
from time import sleep
from haversine import haversine, Unit
from geopy.geocoders import Nominatim
# FIFTEEN = 0.01041666666
# BUFFER = FIFTEEN * (5/3)

locations = dict()
# try:
#     with open('locations' + str(speed) + '.csv', 'r') as locs:
#         line = locs.readline()
#         while line:
#             deets = line.split(',')
#             locations[deets[0]] = (float(deets[1]), deets[2])
#             line = locs.readline()
# except Exception: pass
sp = 0
class TripType(Enum):
    A = 1 # Destination is a home without passenger Must be before B for a location
    B = 2 # Destination is a hospital with passenger Must be before C for a location
    C = 3 # Destination is a hospital without a passenger Must be before D for a location
    D = 4 # Destination is a home with a passenger
    INTER_A = 5 # From driver home to any other location Must occur before any A trips
    INTER_B = 6 # From any location to driver home Must occur after all D trips
class InvalidTripException(Exception):
    pass
class Trip:
    def __init__(self, o, d, space, id, type, start, end, prefix=False, suffix=False, prefixLen=3, suffixLen=4):
        global sp
        self.type = type
        self.id = id
        self.lp = LocationPair(o, d, prefix, suffix, prefixLen, suffixLen)
        self.space = space
        self.start = max(0.0, start)
        self.end = 1.0 if end == 0 else end
        # sp = max(sp, self.lp.miles/((self.end-self.start) * 24))
        # # print("speed needed", self.lp.miles/((self.end-self.start) * 24))
        # if self.lp.time > self.end-self.start >= 0:
        #     # print("not enough time")
        #     raise InvalidTripException()
        #     # print("Not enough speed", self.start, self.end, self.lp.miles, self.lp.time)
        #     # print(self.lp.o, self.lp.d)
        #     # print(self.lp.c1, self.lp.c2)
        #     # exit(1)
        # if self.lp.time > self.end - self.start >= 0:
        #     print(o, d)
        #     if self.type == TripType.B or self.type == TripType.D:
        #         print("Not enough time for primary trip")
        #         exit(1)
        #     raise InvalidTripException()
        # if self.end < self.start:
        #     # print("starts too late")
        #     raise InvalidTripException()
        self.los = 'W' if space == 1.5 else 'A'
    def __repr__(self):
        return self.lp.o + "->" + self.lp.d

class Location:
    def __init__(self, addr, coord = None):
        self.addr = addr
        if coord is None:
            self.coord = self.find_coord(addr)
        else:
            self.coord = coord

    def find_coord(self, addr):
        # geo_api = "78bdef6c2b254abaa78c55640925d3db"
        geo_api = "3c8dd43d76194d28bf62f76a46b305c4"
        geolocator = OpenCageGeocode(geo_api)
        l1loc = geolocator.geocode(addr)
        # print(addr, l1loc)
        return (l1loc[0]['geometry']['lat'], l1loc[0]['geometry']['lng'])

class LocationPair:
    def get_speed(self, miles):
        # return 800
        if miles < 10:
            return 40
        if miles < 30:
            # print(50)
            return 50
        if miles < 50:
            # print(60)
            return 60
        else:
            # print(70)
            return 70

    def __init__(self, l1, l2, prefix, suffix, plen, slen):
        self.o = l1
        self.d = l2
        if prefix:
            l1 = l1[plen:]
        if suffix:
            l1 = l1[:-slen]
        if prefix:
            l2 = l2[plen:]
        if suffix:
            l2 = l2[:-slen]
        self.miles, self.time = self.computeDistance(l1, l2)


    def computeDistance(self, l1, l2):
        # get lat,lon for l1 and l2
        # print(l1,l2)
        if l1 in locations:
            loc1 = locations[l1]
        else:
            loc1 = Location(l1)
            # with open('locations' + str(speed) + '.csv', 'a') as locs:
            #     locs.write(l1 + "," + str(loc1.coord[0]) + "," + str(loc1.coord[1]) + '\n')
            locations[l1] = loc1
            sleep(1)
        if l2 in locations:
            loc2 = locations[l2]
        else:
            loc2 = Location(l2)
            # with open('locations' + str(speed) + '.csv', 'a') as locs:
            #     locs.write(l1 + "," + str(loc2.coord[0]) + "," + str(loc2.coord[1]) + '\n')
            locations[l2] = loc2
        # c1 = str(l1loc[0]['geometry']['lat']) + "," + str(l1loc[0]['geometry']['lng'])
        # c2 = str(l2loc[0]['geometry']['lat']) + "," + str(l2loc[0]['geometry']['lng'])
        # c1 = (l1loc[0]['geometry']['lat'] ,l1loc[0]['geometry']['lng'])
        # c2 = (l2loc[0]['geometry']['lat'],l2loc[0]['geometry']['lng'])
        c1 = loc1.coord
        c2 = loc2.coord
        self.c1 = c1
        self.c2 = c2
        # print(c1, c2)
        miles = haversine(c1,c2, Unit.MILES)
        speed = self.get_speed(miles)
        time = (miles/speed)/24
        if time > 1:
            print(miles, time, speed)
            exit(1)
        return miles, time
        # url = "https://graphhopper.com/api/1/route?point=" + c1 + "&point=" + c2 + "&vehicle=car&locale=de&calc_points=false&key=" + api_key
        # resp = requests.get(url).json()
        # # print(resp["paths"][0]['distance']/1609.344, resp['paths'][0]['time']/60000.0)
        # sleep(1)
        # return resp["paths"][0]['distance']/1609.344, (resp['paths'][0]['time']/60000.0)/(24*60)

