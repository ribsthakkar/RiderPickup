import datetime
from typing import Union, Dict, List

import pandas as pd
from pandas import Series, DataFrame

from avicena.models import MergeAddress, RevenueRate
from avicena.models.MergeAddress import load_merge_details_from_db, load_merge_details_from_csv
from avicena.models.RevenueRate import load_revenue_table_from_db, load_revenue_table_from_csv
from avicena.util.Exceptions import RevenueCalculationException, MissingTripDetailsException
from avicena.util.Geolocator import find_coord_lat_lon
from avicena.util.TimeWindows import get_time_window_by_hours_minutes, timedelta_to_fraction_of_day

INTER_LEG_BUFFER = get_time_window_by_hours_minutes(2, 30)
TRIP_LENGTH_BUFFER = get_time_window_by_hours_minutes(2, 0)


def convert_time(time: Union[float, str]) -> float:
    """
    Standardaize any time input.
    This accepts a string or a float and returns a float that represents the fraction of the day passed for the time of
    day.
    The string must either by directly convertable to a float or in a HH:MM HH:MM:SS format
    :param time: input time
    :return: float representation of the time of day that has passed
    """
    try:
        return float(time)
    except:
        segments = [int(x) for x in time.split(':')]
        if len(segments) <= 2:
            segments.append(0)
            segments.append(0)
            segments.append(0)
        td = datetime.timedelta(hours=segments[0], minutes=segments[1], seconds=segments[2])
        return timedelta_to_fraction_of_day(td)


def _adjust_pickup_dropoff_merge(pickup_time: float, id: str, pickup_address: str, dropoff_times: Series, ids: Series, merge_details: Dict[str, MergeAddress]) -> Series:
    """
    Clean up the pickup and dropoff times for a given trip that was parsed from the inputs
    This function returns a a series with the udpated pickup_time, dropoff_time, and indication of whether it is a merge trip
    :param pickup_time: Original pickup time of input trip
    :param id: ID of input trip. Must end in 'A' , 'B', or 'C'
    :param pickup_address: Pickup address of input trip
    :param dropoff_times: All Trip Dropoff Times
    :param ids: All Trip IDs
    :param merge_details: dictionary mapping address substring to actual MergeAddress object
    :return: Series containing [pickup_time, dropoff_time, is_merge]
    """
    id_mapping = {'B': 'A', 'C': 'B'}
    start_window = INTER_LEG_BUFFER
    is_merge = False
    for merge_address in merge_details:
        if pickup_address in merge_address:
            start_window = timedelta_to_fraction_of_day(merge_details[merge_address].window)
            is_merge = True
            break
    if (pickup_time == 0.0 or pickup_time > 1 - (1 / 24) or is_merge) and (id.endswith('B') or id.endswith('C')):
        pickup_time = dropoff_times[ids == id[:-1] + id_mapping[id[-1]]].iloc[0] + start_window
        return pd.Series([pickup_time, min(1 - (1 / 24), pickup_time + TRIP_LENGTH_BUFFER), is_merge])
    else:
        return pd.Series([pickup_time, min(1 - (1 / 24), pickup_time + TRIP_LENGTH_BUFFER), is_merge])


def _revenue_calculation(table: Dict[str, List[RevenueRate]], miles: float, los: str) -> float:
    """
    Calculate the revenue for a given Level of Service and miles for a trip using the revenue table
    :param table: dictionary mapping level of service to a list of associated revenue rates
    :param miles: miles for a trip
    :param los: level of service of the trip
    :return: revenue earned from the trip
    """
    for revenue_rate in table[los]:
        if revenue_rate.lower_mileage_bound <= miles <= revenue_rate.upper_mileage_bound:
            return revenue_rate.calculate_revenue(miles)
    raise RevenueCalculationException(f"Unable to calculate revenue for level of service:{los} miles:{miles}")


def _get_trip_coordinates(df: DataFrame) -> None:
    """
    Populate dataframe with coordinates of pickup and dropoff addresses
    :param df: Dataframe to update
    """
    df[['trip_pickup_lat', 'trip_pickup_lon']] = df['trip_pickup_address'].apply(
        lambda x: pd.Series(find_coord_lat_lon(x)))
    df[['trip_dropoff_lat', 'trip_dropoff_lon']] = df['trip_dropoff_address'].apply(
        lambda x: pd.Series(find_coord_lat_lon(x)))


def _compute_trip_revenues(df: DataFrame, revenue_table: Dict[str, List[RevenueRate]]) -> None:
    """
    Calculate revenues for all trips
    :param df: dataframe to be updated with trip details
    :param revenue_table: dictionary mapping level of service to a list of associated revenue rates
    """
    df['trip_revenue'] = df[['trip_miles', 'trip_los']].apply(
        lambda x: _revenue_calculation(revenue_table, float(x['trip_miles']), x['trip_los']), axis=1)


def _fill_in_missing_times_and_merge_details(df: DataFrame, merge_details: Dict[str, MergeAddress]) -> None:
    """
    Update the missing travel times, correct for merge trip timings, set the merge indication flags
    :param df: dataframe to be updated with trip details
    :param merge_details: dictionary mapping address substring to actual MergeAddress object
    """
    df[['trip_pickup_time', 'trip_dropoff_time', 'merge_flag']] = \
        df[['trip_pickup_time', 'trip_id', 'trip_pickup_address']].apply(
            lambda x: _adjust_pickup_dropoff_merge(x['trip_pickup_time'], x['trip_id'], x['trip_pickup_address'],
                                                   df['trip_dropoff_time'], df['trip_id'], merge_details), axis=1)


def _standardize_time_format_trip_df(df: DataFrame) -> None:
    """
    Convert all the times stored in the dataframe to floats representing fraction of the day
    :param df: dataframe with trip_pickup_time and trip_dropoff_time
    """
    df['trip_pickup_time'] = df['trip_pickup_time'].apply(convert_time)
    df['trip_dropoff_time'] = df['trip_dropoff_time'].apply(convert_time)


def standardize_trip_df(df: DataFrame, merge_details: Dict[str, MergeAddress], revenue_table: Dict[str, List[RevenueRate]]) -> None:
    """
    Apply time standardization, merge trip updates, missing time updates, revenue calculations, and coordinates to
    the trip dataframe
    :param df: input trip dataframe to be updated
    :param merge_details: dictionary mapping address substring to actual MergeAddress object
    :param revenue_table: dictionary mapping level of service to a list of associated revenue rates
    """
    _standardize_time_format_trip_df(df)
    _fill_in_missing_times_and_merge_details(df, merge_details)
    _compute_trip_revenues(df, revenue_table)
    _get_trip_coordinates(df)


def verify_and_save_parsed_trips_df_to_csv(df: DataFrame, path_to_save: str) -> None:
    """
    Check that all required columns are in the input dataframe of parsed trips (i.e. it has been standardized) and
    save it to the output_directory in a file called 'parsed_trips.csv'
    :param df: dataframe that will be verified and saved to CSV
    :param path_to_save: path to save parsed CSV
    :return:
    """
    required_columns = {'trip_id', 'trip_pickup_address', 'trip_pickup_time', 'trip_pickup_lat', 'trip_pickup_lon',
                        'trip_dropoff_address', 'trip_dropoff_time', 'trip_dropoff_lat', 'trip_dropoff_lon', 'trip_los',
                        'trip_miles', 'merge_flag', 'trip_revenue'}
    for column in required_columns:
        if column not in df.columns:
            raise MissingTripDetailsException(f"Expected {column} to be in dataframe")

    parsed_df = df[required_columns]
    parsed_df.to_csv(path_to_save)