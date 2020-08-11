from avicena.models.Database import create_db_session
from avicena.models.Driver import load_drivers_from_db
from avicena.models.Trip import load_trips_from_df
from avicena.optimizers import PDWTWOptimizer
from avicena.parsers import LogistiCareParser, CSVParser
from avicena.parsers import *
from avicena.util.Exceptions import InvalidConfigException
from avicena.optimizers import *
from datetime import datetime
import yaml

import argparse

parsers = {'LogistiCare': LogistiCareParser, 'Default': CSVParser}
optimizers = {'GeneralOptimizer': GeneralOptimizer, 'PDWTWOptimizer': PDWTWOptimizer}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the Patient Dispatch Model')

    parser.add_argument('-c', '--app-config', action='store', type=int, dest='app_config', default='config/app_config.yaml',
                        help='Path to application config file')

    parser.add_argument('-o', '--opt-config', action='store', type=str, dest='opt_config', default='config/general_optimizer_config.yaml',
                        help='Path to optimizer specific config file')

    parser.add_argument('-n', '--name', action='store', type=str, dest='name', default='Patient Dispatch',
                        help='Name of Model')

    parser.add_argument('-t', '--trips-file', action='store', type=str, dest='trips_file',
                        help='Path to Trips File')

    parser.add_argument('-d', '--driver-ids', nargs='+', type=int, dest='driver_ids',
                        help='List of driver IDs separated by spaces')

    args = parser.parse_args()
    app_config = yaml.load(args.app_config)
    optimizer_config = yaml.load(args.opt_config)

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

    trips_df = trip_parser.parse_trips_to_df(args.trips_file, app_config)
    drivers = load_drivers_from_db(args.driver_ids, db_session)
    trips = load_trips_from_df(trips_df)

    optimizer = optimizer_type(trips, drivers, optimizer_config, app_config['model_name'])
    optimizer.solve(app_config['assignment_file'])
