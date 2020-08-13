import os

from opencage.geocoder import OpenCageGeocode

locations = {}

def find_coord_lat_lon(addr, key=None):
    if key is None:
        key = os.environ.get("GEOCODER_KEY")
    if addr in locations:
        return locations[addr]
    geolocator = OpenCageGeocode(key)
    l1loc = geolocator.geocode(addr)
    try:
        coordinates = (l1loc[0]['geometry']['lat'], l1loc[0]['geometry']['lng'])
        locations[addr] = coordinates
        return coordinates
    except IndexError:
        print("Couldn't find coordinates for ", addr)

def find_coord_lon_lat(addr, key=None):
    return tuple(reversed(find_coord_lat_lon(addr, key)))