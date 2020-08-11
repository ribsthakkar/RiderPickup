from opencage.geocoder import OpenCageGeocode

def find_coord_lat_lon(addr, key):
    geolocator = OpenCageGeocode(key)
    l1loc = geolocator.geocode(addr)
    try:
        return (l1loc[0]['geometry']['lat'], l1loc[0]['geometry']['lng'])
    except IndexError:
        print("Couldn't find coordinates for ", addr)

def find_coord_lon_lat(addr, key):
    return tuple(reversed(find_coord_lat_lon(addr, key)))