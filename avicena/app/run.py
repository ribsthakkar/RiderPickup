import os

from avicena.models.Assignment import generate_visualization_from_csv
from avicena.models.Database import create_db_session
from avicena.models.Driver import load_drivers_from_db, load_drivers_from_csv
from avicena.models.MergeAddress import load_merge_details_from_csv
from avicena.models.RevenueRate import load_revenue_table_from_csv
from avicena.models.Trip import load_trips_from_df
# from avicena.optimizers import PDWTWOptimizer
from avicena.parsers import LogistiCareParser, CSVParser
from avicena.parsers import *
from avicena.util.Exceptions import InvalidConfigException
from avicena.optimizers import *
from datetime import datetime
import yaml

import argparse

from avicena.util.Geolocator import locations

parsers = {'LogistiCare': LogistiCareParser, 'CSV': CSVParser}
optimizers = {'GeneralOptimizer': GeneralOptimizer, 'PDWTWOptimizer': None}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the Patient Dispatch Model')

    parser.add_argument('-c', '--app-config', action='store', type=str, dest='app_config', default='config/app_config.yaml',
                        help='Path to application config file')

    parser.add_argument('-o', '--opt-config', action='store', type=str, dest='opt_config', default='config/general_optimizer_config.yaml',
                        help='Path to optimizer specific config file')

    parser.add_argument('-n', '--name', action='store', type=str, dest='name', default='Patient Dispatch',
                        help='Name of Model')

    parser.add_argument('-d', '--date', action='store', type=str, dest='date', default=datetime.now().strftime('%m-%d-%Y'),
                        help='Date in MM-DD-YYYY format')

    parser.add_argument('-t', '--trips-file', action='store', type=str, dest='trips_file',
                        help='Path to Trips File')

    parser.add_argument('-i', '--driver-ids', nargs='+', type=int, dest='driver_ids',
                        help='List of driver IDs separated by spaces')

    args = parser.parse_args()
    with open(args.app_config) as cfg_file:
        app_config = yaml.load(cfg_file)
    with open(args.opt_config) as cfg_file:
        optimizer_config = yaml.load(cfg_file)

    os.environ['GEOCODER_KEY'] = app_config['geocoder_key']
    db_session = create_db_session(app_config['database'])
    app_config['database']['db_session'] = db_session

    if app_config['trips_parser'] in parsers:
        trip_parser = parsers[app_config['trips_parser']]
    else:
        raise InvalidConfigException(f"Invalid client parser {app_config['client_parser']}")

    if app_config['optimizer'] in optimizers:
        optimizer_type = optimizers[app_config['optimizer']]
    else:
        raise InvalidConfigException(f"Invalid optimizer {app_config['optimizer']}")

    # revenue_table = load_revenue_table_from_db(db_session)
    revenue_table = load_revenue_table_from_csv(app_config['revenue_table_path'])

    # merge_details = load_merge_details_from_db(db_session)
    merge_details = load_merge_details_from_csv(app_config['merge_address_table_path'])

    # drivers = load_drivers_from_db(args.driver_ids, db_session)
    drivers = load_drivers_from_csv(app_config['driver_table_path'], args.driver_ids)

    trips_df = trip_parser.parse_trips_to_df(args.trips_file, merge_details, revenue_table, app_config['output_directory'])
    trips = load_trips_from_df(trips_df, app_config['assumed_driving_speed'])

    optimizer = optimizer_type(trips, drivers, args.name, args.date, float(app_config['assumed_driving_speed']), optimizer_config)
    # print(locations)
    optimizer.solve(app_config['output_directory'] + '/solution.csv')
    generate_visualization_from_csv(app_config['output_directory'] + '/solution.csv', drivers, args.name, app_config['output_directory'] + '/visualization.html', False)

