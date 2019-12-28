from enum import Enum
import requests
from opencage.geocoder import OpenCageGeocode
from time import sleep
from haversine import haversine, Unit
from geopy.geocoders import Nominatim

locations = dict()

class TripType(Enum):
    A = 1 # Destination is a home without passenger Must be before B for a location
    B = 2 # Destination is a hospital with passenger Must be before C for a location
    C = 3 # Destination is a hospital without a passenger Must be before D for a location
    D = 4 # Destination is a home with a passenger
    INTER_A = 5 # From driver home to any other location Must occur before any A trips
    INTER_B = 6 # From any location to driver home Must occur after all D trips

class Trip:
    def __init__(self, o, d, space, id, type, start, end):
        self.type = type
        self.id = id
        self.lp = LocationPair(o, d)
        self.space = space
        self.start = max(0.0, start)
        self.end = 1.0 if end == 0 else end

class Location:
    def __init__(self, addr):
        self.addr = addr
        self.coord = self.find_coord(addr)

    def find_coord(self, addr):
        geo_api = "78bdef6c2b254abaa78c55640925d3db"
        geolocator = OpenCageGeocode(geo_api)
        l1loc = geolocator.geocode(addr)
        # print(addr, l1loc)
        return (l1loc[0]['geometry']['lat'], l1loc[0]['geometry']['lng'])

class LocationPair:
    def __init__(self, l1, l2):
        self.o = l1
        self.d = l2
        if l1[-1] == 'P' or l1[-1] == 'D':
            if self.o[:-1] == self.d[:-1]:
                self.miles, self.time = 0, 0
            else:
                self.miles, self.time = self.computeDistance(self.o[:-1], self.d[:-1])
        else:
            self.miles, self.time = self.computeDistance(self.o, self.d)


    def computeDistance(self, l1, l2):
        # get lat,lon for l1 and l2
        # print(l1,l2)
        if l1 in locations:
            loc1 = locations[l1]
        else:
            loc1 = Location(l1)
            locations[l1] = loc1
            sleep(1)
        if l2 in locations:
            loc2 = locations[l2]
        else:
            loc2 = Location(l2)
            locations[l2] = loc2
        speed = 30
        # c1 = str(l1loc[0]['geometry']['lat']) + "," + str(l1loc[0]['geometry']['lng'])
        # c2 = str(l2loc[0]['geometry']['lat']) + "," + str(l2loc[0]['geometry']['lng'])
        # c1 = (l1loc[0]['geometry']['lat'] ,l1loc[0]['geometry']['lng'])
        # c2 = (l2loc[0]['geometry']['lat'],l2loc[0]['geometry']['lng'])
        c1 = loc1.coord
        c2 = loc2.coord
        # print(c1, c2)
        miles = haversine(c1,c2, Unit.MILES)
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

