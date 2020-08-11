import datetime
import random

import pandas as pd

def load_trips(processed_trips_file='calc_trips.csv', assumptions=None):
    trip_df = pd.read_csv(processed_trips_file)
    trips = []
    for index, row in trip_df.iterrows():
        o = row['trip_pickup_address'] + "P" + str(hash(row['trip_id']))[1:4]
        d = row['trip_dropoff_address'] + "D" + str(hash(row['trip_id']))[1:4]
        start = convert_time(str(row['trip_pickup_time']))
        end = convert_time(str(row['trip_dropoff_time']))
        cap = 1 if row['trip_los'] == 'A' else 1.5
        id = row['trip_id']
        rev = float(row['trip_rev'])
        lp = LocationPair(o, d, (float(row['orig_lat']), float(row['orig_long'])),
                          (float(row['dest_lat']), float(row['dest_long'])))
        # AB Merge Assumption
        if row['merge_flag']:
            typ = TripType.MERGE
        else:
            typ = None
        trips.append(Trip(o, d, cap, id, typ, start, end, rev, preset_miles=int(row['scheduled_miles']), lp=lp))
    return trips

def convert_time(time):
    try:
        return float(time)
    except:
        segments = [int(x) for x in time.split(':')]
        if len(segments) <= 2:
            segments.append(0)
            segments.append(0)
            segments.append(0)
        x = datetime.timedelta(hours=segments[0], minutes=segments[1], seconds=segments[2])
        return x.total_seconds() / (60 * 60 * 24)

def load_assignment_drivers_from_db(driver_ids, date=None):
    db_drivers = list(map(Driver.query.get, driver_ids))
    drivers = []
    for index, d in enumerate(db_drivers):
        cap = 1 if d.level_of_service == 'A' else 1.5
        add = d.address + "DR" + str(hash(d.id))[1:3]
        if date is None:
            day_of_week = datetime.datetime.now().timetuple().tm_wday
        else:
            m, d, y = date.split('-')
            day_of_week = datetime.datetime(int(y), int(m), int(d)).timetuple().tm_wday
        early_day_flag = day_of_week % 2 != d.early_day_flag
        drivers.append(Driver(d.id, d.name, add, cap, d.level_of_service, early_day_flag))
    if not any(d.early_day_flag for d in drivers):
        x = random.choice(drivers)
        while x.early_day_flag:
            x = random.choice(drivers)
        x.early_day_flag = True
    return drivers

def load_drivers_from_csv(drivers_file, date=None):
    driver_df = pd.read_csv(drivers_file)
    drivers = []
    for index, row in driver_df.iterrows():
        if row['Available?'] != 1:
            continue
        cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
        add = row['Address'] + "DR" + str(hash(row['ID']))[1:3]
        if date is None:
            day_of_week = datetime.datetime.now().timetuple().tm_wday
        else:
            m, d, y = date.split('-')
            day_of_week = datetime.datetime(int(y), int(m), int(d)).timetuple().tm_wday
        early_day_flag = day_of_week % 2 != int(row['Early Day'])
        drivers.append(Driver(row['ID'], row['Name'], add, cap, row['Vehicle_Type'], early_day_flag))
    if not any(d.early_day_flag for d in drivers):
        x = random.choice(drivers)
        while x.early_day_flag:
            x = random.choice(drivers)
        x.early_day_flag = True
    return drivers
