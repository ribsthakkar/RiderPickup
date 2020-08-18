import os
import random
from typing import Type, Union, Dict, List, Any
import yaml
import argparse

from pandas import DataFrame
from sqlalchemy.orm import Session

from avicena.models.Assignment import generate_visualization_from_df, load_assignment_from_df
from avicena.util.Database import create_db_session, save_and_commit_to_db, close_db_session
from avicena.models.Driver import load_drivers_from_db, load_drivers_from_csv, prepare_drivers_for_optimizer, Driver
from avicena.models.MergeAddress import load_merge_details_from_csv, load_merge_details_from_db, MergeAddress
from avicena.models.RevenueRate import load_revenue_table_from_csv, load_revenue_table_from_db, RevenueRate
from avicena.models.Trip import load_and_filter_valid_trips_from_df, Trip
from avicena.parsers import LogistiCareParser, CSVParser
from avicena.util.ConfigValidation import validate_app_config
from avicena.util.Exceptions import InvalidConfigException
from avicena.optimizers.GeneralOptimizer import GeneralOptimizer
from datetime import datetime

from avicena.util.ParserUtil import verify_and_save_parsed_trips_df_to_csv

# Supported Parser and Optimizer types that will be passed into the Config file
parsers = {'LogistiCare': LogistiCareParser, 'CSV': CSVParser}
optimizers = {'GeneralOptimizer': GeneralOptimizer}


def _run_parser(trip_parser: Union[Type[LogistiCareParser], Type[CSVParser]], trips_file: str,
                revenue_table: Dict[str, List[RevenueRate]], merge_details: Dict[str, MergeAddress], assumed_speed: int,
                model_name: str, output_directory: str) -> List[Trip]:
    """
    Parses the trips from the trips file, verifies the parsing and saves it to a file in the output directory called
    "parsed_trips.csv", and filters out invalid trips and all legs associated with the invalid trips.
    :param trip_parser: Type of TripParser loaded from config
    :param trips_file: File with trip details
    :param revenue_table: Map from level of service to RevenueRate objects
    :param merge_details: Map from merge address to MergeAddress objects
    :param assumed_speed: Assumed Driving Speed to determine travel times
    :param model_name: Name for this run
    :param output_directory: Directory where the parsed files will be written
    :return: List of Trips that are valid and populated with all necessary details.
    """
    trips_df = trip_parser.parse_trips_to_df(trips_file, merge_details, revenue_table, output_directory)
    verify_and_save_parsed_trips_df_to_csv(trips_df, output_directory + "/" + model_name + "_parsed_trips.csv")
    trips = load_and_filter_valid_trips_from_df(trips_df, assumed_speed)
    return trips


def _run_optimizer(trip_optimizer: Union[Type[GeneralOptimizer]], trips: List[Trip], drivers: List[Driver], name: str,
                   date: str, assumed_speed: int, optimizer_config: Dict[str, Any], output_directory: str) -> DataFrame:
    """
    Initializes and runs the optimizer
    :param trip_optimizer: Type of Optimizer to be used
    :param trips: List of parsed and validated trips
    :param drivers: List of filtered and drivers prepared for optimzier
    :param name: Name for this run
    :param date: Date for which this model is used
    :param assumed_speed: Assumed Driving Speed
    :param optimizer_config: Loaded optimizer specific configuratiod
    :param output_directory: Directory where the solution.csv and other file generated while solving are stored
    :return: DataFrame with the solution of the model containing the original trip details as well estimated pickups,
            estimated dropoffs, and driver assigned to the trip
    """
    optimizer = trip_optimizer(trips, drivers, name, date, assumed_speed, optimizer_config)
    solution = optimizer.solve(output_directory + '/solution.csv')
    return solution


def _retrieve_database_inputs(db_session: Session) -> (
Dict[str, List[RevenueRate]], Dict[str, MergeAddress], List[Driver]):
    """
    Retrieve the static inputs of the model from the database
    :param db_session: SQLAlchemy Database connection session
    :return: level of service mapped to List of RevenueRate objects, merge addresses mapped to MergeAddress objects,
                 List of driver objects
    """
    revenue_table = load_revenue_table_from_db(db_session)
    merge_details = load_merge_details_from_db(db_session)
    drivers_table = load_drivers_from_db(db_session)

    return revenue_table, merge_details, drivers_table


def _retrieve_csv_inputs(app_config: Dict[str, Any]) -> (
Dict[str, List[RevenueRate]], Dict[str, MergeAddress], List[Driver]):
    """
    Retrieve static inputs of the model from CSV files
    :param app_config: App Configuration
    :return: level of service mapped to List of RevenueRate objects, merge addresses mapped to MergeAddress objects,
                List of driver objects
    """
    revenue_table = load_revenue_table_from_csv(app_config['revenue_table_path'])
    merge_details = load_merge_details_from_csv(app_config['merge_address_table_path'])
    drivers_table = load_drivers_from_csv(app_config['driver_table_path'])

    return revenue_table, merge_details, drivers_table


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the Patient Dispatch Model')
    required_named = parser.add_argument_group('required arguments')

    required_named.add_argument('-n', '--name', action='store', type=str, dest='name', default='Patient Dispatch',
                                help='Name of Model')

    required_named.add_argument('-s', '--speed', action='store', type=int, dest='speed', default=50,
                                help='Assumed Traveling Speed in MPH')

    required_named.add_argument('-d', '--date', action='store', type=str, dest='date',
                                default=datetime.now().strftime('%m-%d-%Y'),
                                help='Date in MM-DD-YYYY format')

    required_named.add_argument('-t', '--trips-file', action='store', type=str, dest='trips_file',
                                help='Path to Trips File')

    required_named.add_argument('-i', '--driver-ids', nargs='+', type=int, dest='driver_ids',
                                help='List of driver IDs separated by spaces')

    args = parser.parse_args()
    with open('config/app_config.yaml') as cfg_file:
        app_config = yaml.load(cfg_file, Loader=yaml.FullLoader)
    validate_app_config(app_config)

    with open('config/optimizer_config.yaml') as cfg_file:
        optimizer_config = yaml.load(cfg_file, Loader=yaml.FullLoader)

    os.environ['GEOCODER_KEY'] = app_config['geocoder_key']
    random.seed(app_config['seed'])

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
        revenue_table, merge_details, drivers_table = _retrieve_database_inputs(db_session)
        trips = _run_parser(trip_parser, args.trips_file, revenue_table, merge_details, args.speed, args.name,
                            app_config['output_directory'])
        drivers = prepare_drivers_for_optimizer(drivers_table, args.driver_ids, args.date)
        solution = _run_optimizer(trip_optimizer, trips, drivers, args.name, args.date, args.speed, optimizer_config,
                                  app_config['output_directory'])
        save_and_commit_to_db(db_session, load_assignment_from_df(solution, drivers, args.name))
        generate_visualization_from_df(solution, drivers, args.name,
                                       app_config['output_directory'] + '/visualization.html', False)
        close_db_session(db_session)
    else:
        revenue_table, merge_details, drivers_table = _retrieve_csv_inputs(app_config)
        trips = _run_parser(trip_parser, args.trips_file, revenue_table, merge_details, args.speed,
                            app_config['output_directory'])
        drivers = prepare_drivers_for_optimizer(drivers_table, args.driver_ids, args.date)
        solution = _run_optimizer(trip_optimizer, trips, drivers, args.name, args.date, args.speed, optimizer_config,
                                  app_config['output_directory'])
        generate_visualization_from_df(solution, drivers, args.name,
                                       app_config['output_directory'] + '/visualization.html', False)
