import os
from typing import Optional
import logging
from opencage.geocoder import OpenCageGeocode

locations = {}

log = logging.getLogger(__name__)


def find_coord_lat_lon(addr: str, key: Optional[str] = None) -> (float, float):
    """
    Find the latitude and longitude for an address
    :param addr: Address to geocode
    :param key: optional string for geocoder key
    :return: Latitude, Longitude of address
    """
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
        log.warning(f"Couldn't find coordinates for  {addr}")


def find_coord_lon_lat(addr: str, key: Optional[str] = None) -> (float, float):
    """
    Find the longitude and latitude for an address
    :param addr: Address to geocode
    :param key: optional string for geocoder key
    :return: Longitude, Latitude of address
    """
    return tuple(reversed(find_coord_lat_lon(addr, key)))
