import pandas as pd

from avicena.util.ParserUtil import standardize_trip_df


def parse_trips_to_df(trips_file, merge_details, revenue_table, output_directory):
    df = pd.read_csv(trips_file)
    standardize_trip_df(df, merge_details, revenue_table)
    print(f"Parsed {len(df)} Trips")
    return df
