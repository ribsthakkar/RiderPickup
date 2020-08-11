import pandas as pd

from avicena.util.ParserUtil import standardize_df


def parse_trips_to_df(trips_file, config):
    df = pd.read_csv(trips_file)
    standardize_df(df, config)
    return df
