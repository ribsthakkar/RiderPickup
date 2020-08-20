from enum import Enum

from haversine import haversine, Unit
from opencage.geocoder import OpenCageGeocode

from experimental.constants import *

try:
    from locations import locations_cache

    locations = locations_cache  # cached dict mapping an address to its lat long, not in repository for privacy
except:
    locations = {'134 E 2nd Ave , Taylor , TX 76574': (30.5657537, -97.3937946),
                 '16010 Park Valley Dr , Apt . 100 , Round Rock , TX 78681-3574': (30.512862, -97.711188),
                 '9345 E Highway 290 , Apt . 12102 , Bldg . 12 , Austin , TX 78724-2463': (30.329392, -97.64733),
                 '1801 E 51st St , Bldg . G , Austin , TX 78723-3434': (30.305428, -97.702329),
                 'x 85 Trinity St , Apt . 811 , Bldg . No // No Gc , Austin , TX 78701': (30.197644, -97.7491),
                 '1631 E 2nd St , Bldg . C , Austin , TX 78702-4490': (30.259142, -97.72774),
                 '400 E Cypress Creek Rd , Apt . 1103 , Bldg . No // No Gc , Cedar Park , TX 78613': (
                 30.048154, -98.35584),
                 '1631 E 2nd St , Bldg . A C & D , Austin , TX 78702-4490': (30.259142, -97.72774),
                 '11020 Dessau Rd , Austin , TX 78754-2053': (30.4027877, -97.6388753),
                 '2606 W Pecan St , Apt . 300 , Bldg . 3 , Pflugerville , TX 78660-1917': (30.449825, -97.658057),
                 '2806 Real St , Austin , TX 78722': (30.282913, -97.7119655),
                 '1801 E 51st St , Austin , TX 78723-3434': (30.3010094, -97.6985202),
                 '110 E Live Oak St , Austin , TX 78704': (30.2419797, -97.7514697),
                 '2800 S I H 35 , Apt . 120 , Austin , TX 78704-5700': (30.218854, -97.750234),
                 '1416 Mangrum St , Pflugerville , TX 78660': (30.444169, -97.659798),
                 '2129 W Pecan St , Pflugerville , TX 78660': (30.445484, -97.649736),
                 '508 E Howard Ln , Apt . LOT 319 , Austin , TX 78753-9704': (30.409607, -97.64855),
                 '10000 Metric Blvd , Austin , TX 78758-5202': (30.3802058, -97.7165808),
                 '7510 Lazy Creek Dr , Apt . B , Bldg . 5 , Austin , TX 78724-3300': (30.315474, -97.65692),
                 '1304 Webberwood Way ,  Mobile Home , Elgin , TX 78621-5246': (30.223948, -97.487572),
                 '6114 S First St , Austin , TX 78745-4008': (30.202407, -97.784597),
                 '2213 Santa Maria St , Austin , TX 78702-4615': (30.2578565, -97.7187487),
                 '1701 W Ben White Blvd , Austin , TX 78704-7667': (30.2268293, -97.7828497),
                 '5401 Spring Meadow Rd ,  A ,  Duplex , Austin , TX 78744': (30.19618, -97.735356),
                 '16701 N Heatherwilde B ,  516 ,  5 Ii  , Pflugerville , TX 7866': (30.413328, -97.646238),
                 '1801 E 51st St ,  100 ,  G , Austin , TX 78723-3434': (30.305428, -97.702329),
                 '12433 Dessau Rd ,  602 ,  Unit 3152 , Austin , TX 78754- 0021': (30.396522, -97.642911),
                 '1631 E 2nd St ,  A C & D , Austin , TX 78702-4490': (30.259142, -97.72774),
                 '1636 E 3rd St ,  103 ,  No , Austin , TX 78702': (30.260152, -97.727137),
                 '1631 E 2nd St ,  A , Austin , TX 78702-4490': (30.258913, -97.727466),
                 '9933 Milla Cir ,  House , Austin , TX 78748-3905': (30.1618354, -97.7976865),
                 '1221 W Ben White Blvd ,  200 , Austin , TX 78704-7192': (30.227302, -97.77835),
                 '1214 Southport Dr ,  D , Austin , TX 78704': (30.232307, -97.7766741),
                 '2800 S I H 35 , Austin , TX 78704-5700': (30.3557599, -97.6890565),
                 '5301 W Duval Rd ,  406 A ,  Code 5301 , Austin , TX 78727- 6618': (30.417285, -97.750034),
                 '8010 N Interstate 35 ,  121 , Austin , TX 78753': (30.388382, -97.672564),
                 '1701 W Ben White Blvd ,  180 , Austin , TX 78704-7667': (30.227818, -97.784649),
                 '1601 Royal Crest Dr ,  2160 ,  8/ , Austin , TX 78741- 2848': (30.237574, -97.731207),
                 '706 W Ben White Blvd ,  100 , Austin , TX 78704-8124': (30.226898, -97.770735),
                 '13838 The Lakes Blvd, Pflugerville, TX 78660': (30.4233445, -97.6656668),
                 '1733 Arial Dr, Austin, TX': (30.3918023, -97.6491909),
                 '16010 Park Valley Dr ,  100 , Round Rock , TX 78681-3574': (30.512862, -97.711188),
                 '9345 E Highway 290 ,  12102 ,  12 , Austin , TX 78724-2463': (30.278098, -97.685082),
                 '1801 E 51st St ,  G , Austin , TX 78723-3434': (30.3010094, -97.6985202),
                 '6301 Berkman Dr ,  206 ,  No/  , Austin , TX 78723': (30.316869, -97.690829),
                 '1500 Red River St , Austin , TX 78701': (30.276589, -97.7345157),
                 '303 E Brenham St ,  B ,  Duplex , Manor , TX 78653': (30.337426, -97.556906),
                 '2410 Round Rock Ave ,  150 , Round Rock , TX 78681-4003': (30.509384, -97.712457),
                 '5701 Tracy Lynn Ln ,  B ,  Duplex , Austin , TX 78721': (30.255844, -97.688515),
                 '1010 W 40th St , Austin , TX 78756-4010': (30.308401, -97.741926),
                 '1304 S Webberwood Way ,  2 ,  Mobile Home , Elgin , TX 78621-5246': (30.223948, -97.487572),
                 '5717 Balcones Dr , Austin , TX 78731-4203': (30.338, -97.756495),
                 '2606 W Pecan St ,  300 ,  3 , Pflugerville , TX 78660-1917': (30.449825, -97.658057),
                 'xcell 1806 Harvey St ,  House , Austin , TX 78702-1663': (30.281568, -97.705418),
                 'xbus 8220 Cross Park Dr ,  100 , Austin , TX 78754-5228': (30.335443, -97.669293),
                 '2800 S I H 35 ,  120 , Austin , TX 78704-5700': (30.218854, -97.750234),
                 '3226 W Slaughter Ln ,  127 , Austin , TX 78748': (30.181096, -97.84445),
                 '1631 E 2nd St ,  D , Austin , TX 78702-4490': (30.258913, -97.727466),
                 '12221 N Mopac Exwy , Austin , TX 78758': (30.413874, -97.706466),
                 '508 E Howard Ln ,  LOT 319 , Austin , TX 78753-9704': (30.4174122, -97.6512382),
                 '12433 Dessau Rd ,  2142 ,  B   , Austin , TX 78754- 2183': (30.404676, -97.637745),
                 '4681 College Park Dr , Round Rock , TX 78665': (30.5641494, -97.6568948),
                 '1638 E 2nd St ,  413 , Austin , TX 78702': (30.259224, -97.727542),
                 '2911 Medical Arts St ,  9 , Austin , TX 78705': (30.289351, -97.728493),
                 '14610 Menifee St ,  House , Austin , TX 78725-4718': (30.233446, -97.588285),
                 '4614 N I-35 , Austin , TX 78751': (30.304022, -97.714198),
                 '6200 Loyola Ln ,  424 ,  4  Gc : 2007 , Austin , TX 78724- 3500': (30.197384, -97.748202),
                 '5200 Davis Ln ,  200 ,  B , Austin , TX 78749': (30.207621, -97.860453),
                 '2724 Philomena St ,  123 ,  No , Austin , TX 78723': (30.305107, -97.686631),
                 '8913 Collinfield Dr ,  1 ,  , Austin , TX 78758-6704': (30.360677, -97.70592),
                 '18112 moreto loop, pflugerville, tx 78660': (29.873711, -97.680043),
                 '12151 N ih 35, austin, tx 78753': (30.388382, -97.672564)}

    pass


class TripType(Enum):
    A = 1  # Destination is a home without passenger Must be before B for a location
    B = 2  # Destination is a hospital with passenger Must be before C for a location
    C = 3  # Destination is a hospital without a passenger Must be before D for a location
    D = 4  # Destination is a home with a passenger
    INTER_A = 5  # From driver home to any other location Must occur before any A trips
    INTER_B = 6  # From any location to driver home Must occur after all D trips
    MERGE = 7


class InvalidTripException(Exception):
    pass


class Trip:
    def __init__(self, o, d, space, id, type, start, end, rev=0, preset_miles=0, lp=None, prefix=False, suffix=False,
                 prefixLen=3, suffixLen=4):
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
            raise InvalidTripException(
                "Trip ID:" + str(id) + " start:" + str(start) + " end:" + str(end) + " trip length: " + str(
                    self.lp.time))
        self.preset_m = preset_miles

    def __repr__(self):
        return self.lp.o + "->" + self.lp.d


class Location:
    def __init__(self, addr, coord=None):
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
        if addr.endswith('Aust'):
            addr = addr.replace('Aust', 'Austin, TX').replace('B', 'Blvd')
        geo_api = keys['geo_key']
        geolocator = OpenCageGeocode(geo_api)
        l1loc = geolocator.geocode(addr)
        try:
            return (l1loc[0]['geometry']['lat'], l1loc[0]['geometry']['lng'])
        except IndexError:
            print("Couldn't find coordinates for ", addr)

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
        self.time = (self.miles / speed) / 24 + FIFTEEN / 15
        if self.time > 1:
            print("Time Longer than a Day")
            print(self.o, self.c1)
            print(self.d, self.c2)
            print(self.miles, self.time, speed)
            exit(1)

    def getCoords(self, l1):
        return Location(l1).coord

    def get_speed(self, miles):
        return SPEED[0]  # Adjust speed if needed
        # if miles < 30:
        #     # print(50)
        #     return 50
        # if miles < 50:
        #     # print(60)
        #     return 60
        # else:
        #     # print(70)
        #     return 70
