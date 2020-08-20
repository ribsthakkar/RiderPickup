import os
import random
from types import ModuleType
from typing import Union, Type, List, Dict, Any
import logging.config
import yaml
from pandas import DataFrame
from sqlalchemy.orm import Session

from avicena.app import OPTIMIZER_CONFIG_FILE, APP_CONFIG_FILE, LOG_CONFIG_FILE
from avicena.models.Driver import Driver, load_drivers_from_db, load_drivers_from_csv
from avicena.models.MergeAddress import MergeAddress, load_merge_details_from_db, load_merge_details_from_csv
from avicena.models.RevenueRate import RevenueRate, load_revenue_table_from_db, load_revenue_table_from_csv
from avicena.models.Trip import Trip, load_and_filter_valid_trips_from_df
from avicena.optimizers import GeneralOptimizer
from avicena.util.ConfigValidation import validate_app_config
from avicena.util.ParserUtil import verify_and_save_parsed_trips_df_to_csv


def run_parser(trip_parser: Union[Type[ModuleType]], trips_file: str,
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


def run_optimizer(trip_optimizer: Union[Type[GeneralOptimizer]], trips: List[Trip], drivers: List[Driver], name: str,
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


def retrieve_database_inputs(db_session: Session) -> (
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


def retrieve_csv_inputs(app_config: Dict[str, Any]) -> (
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


def init_logging() -> None:
    """
    Initialize the loggers for the app
    """
    with open(LOG_CONFIG_FILE, 'r') as cfg_file:
        log_config = yaml.load(cfg_file, Loader=yaml.FullLoader)
        log_config['disable_existing_loggers'] = False
        logging.config.dictConfig(log_config)


def load_app_config() -> Dict[str, Any]:
    """
    Load the application config
    :return: Dict representation of YAML config
    """
    with open(APP_CONFIG_FILE, 'r') as cfg_file:
        app_config = yaml.load(cfg_file, Loader=yaml.FullLoader)
    validate_app_config(app_config)
    os.environ['GEOCODER_KEY'] = app_config['geocoder_key']
    random.seed(app_config['seed'])
    return app_config


def load_optimizer_config() -> Dict[str, Any]:
    """
    Load the optimizer specific config
    :return: Dict representation of YAML config
    """
    with open(OPTIMIZER_CONFIG_FILE, 'r') as cfg_file:
        optimizer_config = yaml.load(cfg_file, Loader=yaml.FullLoader)
    return optimizer_config
