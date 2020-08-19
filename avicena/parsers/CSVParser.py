from typing import Dict, List

import pandas as pd
from pandas import DataFrame

from avicena.models.RevenueRate import RevenueRate
from avicena.models.MergeAddress import MergeAddress
from avicena.util.ParserUtil import standardize_trip_df


def parse_trips_to_df(trips_file: str, merge_details: Dict[str, MergeAddress],
                      revenue_table: Dict[str, List[RevenueRate]],
                      output_directory: str) -> DataFrame:
    """
    Parse the CSV Input format to a standardized DataFrame
    The CSV input header must match the one shown in sample_data/sample_trips.csv
    :param trips_file: input csv file
    :param merge_details: dictionary mapping address substring to actual MergeAddress object
    :param revenue_table: dictionary mapping level of service to a list of associated revenue rates
    :param output_directory: [Ignored]
    :return: DataFrame with parsed trip details
    """
    df = pd.read_csv(trips_file)
    standardize_trip_df(df, merge_details, revenue_table)
    print(f"Parsed {len(df)} Trips")
    return df
