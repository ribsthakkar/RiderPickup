import datetime

from avicena.models.MergeAddress import load_merge_details_from_db
from avicena.models.RevenueRate import load_revenue_table_from_db, load_revenue_table_from_csv
from avicena.util.Exceptions import RevenueCalculationException
from avicena.util.Geolocator import find_coord_lat_lon
from avicena.util.TimeWindows import get_time_window_by_hours_minutes

INTER_LEG_BUFFER = get_time_window_by_hours_minutes(2, 30)
TRIP_LENGTH_BUFFER = get_time_window_by_hours_minutes(2, 0)


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


def _adjust_pickup_dropoff_merge(pickup_time, id, pickup_address, dropoff_times, ids, merge_details):
    id_mapping = {'B': 'A', 'C': 'B'}
    start_window = INTER_LEG_BUFFER
    is_merge = False
    for merge_address in merge_details:
        if pickup_address in merge_address:
            start_window = merge_details[merge_address]
            is_merge = True
            break
    if pickup_time == 0.0 or pickup_time > 1 - (1 / 24) and (id.endswith('B') or id.endswith('C')):
        pickup_time = dropoff_times[ids == id[:-1] + id_mapping[id[-1]]].iloc[0] + start_window
        return pickup_time, min(1 - (1 / 24), pickup_time + TRIP_LENGTH_BUFFER), is_merge
    else:
        return pickup_time, min(1 - (1 / 24), pickup_time + TRIP_LENGTH_BUFFER), is_merge


def _revenue_calculation(table, miles, los):
    for revenue_rate in table[los]:
        if revenue_rate.lower_mileage_bound <= miles <= revenue_rate.upper_mileage_bound:
            return revenue_rate.revenue_per_mile * miles
    raise RevenueCalculationException(f"Unable to calculate revenue for level of service:{los} miles:{miles}")


def standardize_df(df, config):
    df['trip_pickup_time'] = df['trip_pickup_time'].apply(convert_time)
    df['trip_dropoff_time'] = df['trip_dropoff_time'].apply(convert_time)

    # merge_details = load_merge_details_from_db(config['database']['db_session'])
    merge_details = load_merge_details_from_csv(config['merge_details_path'])
    df['trip_pickup_time', 'trip_dropoff_time', 'merge_flag'] = \
        df[['trip_pickup_time', 'trip_id', 'trip_pickup_address']].apply(
            lambda x: _adjust_pickup_dropoff_merge(x['trip_pickup_time'], x['trip_id'], x['trip_pickup_address'],
                                                   df['trip_dropoff_time'], df['trip_id'], merge_details), axis=1)

    # revenue_table = load_revenue_table_from_db(config['database']['db_session'])
    revenue_table = load_revenue_table_from_csv(config['revenue_table_path'])
    df['trip_revenue'] = df[['trip_miles', 'trip_los']].apply(
        lambda x: _revenue_calculation(revenue_table, x['trip_miles'], x['trip_los']), axis=1)

    df['trip_pickup_lat', 'trip_pickup_lon'] = df['trip_pickup_address'].apply(
        lambda x: find_coord_lat_lon(x))
    df['trip_dropoff_lat', 'trip_dropoff_lon'] = df['trip_dropoff_address'].apply(
        lambda x: find_coord_lat_lon(x))