import argparse
from datetime import datetime
from avicena.app.run_common import retrieve_database_inputs, run_parser, run_optimizer, retrieve_csv_inputs, \
    load_optimizer_config, load_app_config, init_logging
from avicena.models.Assignment import generate_visualization_from_df, load_assignment_from_df
from avicena.models.Driver import prepare_drivers_for_optimizer
from avicena.optimizers.GeneralOptimizer import GeneralOptimizer
from avicena.parsers import LogistiCareParser, CSVParser
from avicena.util.Database import create_db_session, save_and_commit_to_db, close_db_session
from avicena.util.Exceptions import InvalidConfigException

# Supported Parser and Optimizer types that will be passed into the Config file
parsers = {'LogistiCare': LogistiCareParser, 'CSV': CSVParser}
optimizers = {'GeneralOptimizer': GeneralOptimizer}


def avicena_run_cli():
    init_logging()
    parser = argparse.ArgumentParser(description='Run the Patient Dispatch Model')
    required_named = parser.add_argument_group('required arguments')

    required_named.add_argument('-n', '--name', action='store', type=str, dest='name', default='PatientDispatch',
                                help='Name of Model')

    required_named.add_argument('-s', '--speed', action='store', type=int, dest='speed', default=50,
                                help='Assumed Traveling Speed in MPH')

    required_named.add_argument('-d', '--date', action='store', type=str, dest='date',
                                default=datetime.now().strftime('%m-%d-%Y'),
                                help='Date in MM-DD-YYYY format')

    required_named.add_argument('-t', '--trips-file', action='store', type=str, dest='trips_file',
                                default='sample_data/sample_trips.csv',
                                help='Path to Trips File')

    required_named.add_argument('-i', '--driver-ids', nargs='+', type=int, dest='driver_ids',
                                default=[101, 102, 103, 104],
                                help='List of driver IDs separated by spaces')

    args = parser.parse_args()
    app_config = load_app_config()
    optimizer_config = load_optimizer_config()

    if app_config['trips_parser'] in parsers:
        trip_parser = parsers[app_config['trips_parser']]
    else:
        raise InvalidConfigException(f"Invalid client parser {app_config['client_parser']}")

    if app_config['optimizer'] in optimizers:
        trip_optimizer = optimizers[app_config['optimizer']]
    else:
        raise InvalidConfigException(f"Invalid optimizer {app_config['optimizer']}")

    database_enabled = app_config['database']['enabled']
    if database_enabled:
        db_session = create_db_session(app_config['database'])
        app_config['database']['db_session'] = db_session
        revenue_table, merge_details, drivers_table = retrieve_database_inputs(db_session)
        trips = run_parser(trip_parser, args.trips_file, revenue_table, merge_details, args.speed, args.name,
                           app_config['output_directory'])
        drivers = prepare_drivers_for_optimizer(drivers_table, args.driver_ids, args.date)
        solution = run_optimizer(trip_optimizer, trips, drivers, args.name, args.date, args.speed, optimizer_config,
                                 app_config['output_directory'])
        save_and_commit_to_db(db_session, load_assignment_from_df(solution, drivers, args.name))
        generate_visualization_from_df(solution, drivers, args.name,
                                       app_config['output_directory'] + '/visualization.html', False)
        close_db_session(db_session)
    else:
        revenue_table, merge_details, drivers_table = retrieve_csv_inputs(app_config)
        trips = run_parser(trip_parser, args.trips_file, revenue_table, merge_details, args.speed,
                           args.name, app_config['output_directory'])
        drivers = prepare_drivers_for_optimizer(drivers_table, args.driver_ids, args.date)
        solution = run_optimizer(trip_optimizer, trips, drivers, args.name, args.date, args.speed, optimizer_config,
                                 app_config['output_directory'])
        generate_visualization_from_df(solution, drivers, args.name,
                                       app_config['output_directory'] + '/visualization.html', False)


if __name__ == "__main__":
    avicena_run_cli()
