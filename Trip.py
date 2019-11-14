from enum import Enum
import requests
from opencage.geocoder import OpenCageGeocode
from time import sleep
from geopy.geocoders import Nominatim

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


class LocationPair:
    def __init__(self, l1, l2):
        self.o = l1
        self.d = l2
        self.miles, self.time = self.computeDistance(l1, l2)


    def computeDistance(self, l1, l2):
        api_key = "40c83aa3-735d-4d4f-b205-e7c1590b7550"
        geo_api = "10f1e06a3c004d2a9106cdf80bc09be3"
        # get lat,lon for l1 and l2
        print(l1,l2)
        geolocator = OpenCageGeocode(geo_api)
        l1loc = geolocator.geocode(l1)
        sleep(1)
        l2loc = geolocator.geocode(l2)
        c1 = str(l1loc[0]['geometry']['lat']) + "," + str(l1loc[0]['geometry']['lng'])
        c2 = str(l2loc[0]['geometry']['lat']) + "," + str(l2loc[0]['geometry']['lng'])
        print(c1, c2)
        url = "https://graphhopper.com/api/1/route?point=" + c1 + "&point=" + c2 + "&vehicle=car&locale=de&calc_points=false&key=" + api_key
        resp = requests.get(url).json()
        # print(resp["paths"][0]['distance']/1609.344, resp['paths'][0]['time']/60000.0)
        sleep(1)
        return resp["paths"][0]['distance']/1609.344, (resp['paths'][0]['time']/60000.0)/(24*60)

