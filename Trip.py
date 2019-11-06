from enum import Enum
import requests
from geopy.geocoders import Nominatim

class TripType(Enum):
    A = 1
    B = 2
    INTER = 3

class Trip:
    def __init__(self, o, d, space, id, type, start, end):
        self.type = type
        self.id = id
        self.lp = LocationPair(o, d)
        self.space = space
        self.start = max(0.0, start)
        self.end = end


class LocationPair:
    def __init__(self, l1, l2):
        self.o = l1
        self.d = l2
        self.miles, self.time = self.computeDistance(l1, l2)


    def computeDistance(self, l1, l2):
        api_key = "40c83aa3-735d-4d4f-b205-e7c1590b7550"
        # get lat,lon for l1 and l2
        geolocator = Nominatim(user_agent="OR Project")
        l1loc = geolocator.geocode(l1)
        l2loc = geolocator.geocode(l2)

        c1 = str(l1loc.latitude) + "," + str(l1loc.longitude)
        c2 = str(l2loc.latitude) + "," + str(l2loc.longitude)
        print(c1, c2)
        url = "https://graphhopper.com/api/1/route?point=" + c1 + "&point=" + c2 + "&vehicle=car&locale=de&calc_points=false&key=" + api_key
        resp = requests.get(url).json()
        print(resp["paths"][0]['distance']/1609.344, resp['paths'][0]['time']/60000.0)
        return resp["paths"][0]['distance']/1609.344, (resp['paths'][0]['time']/60000.0)/(24*60)

