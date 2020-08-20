from typing import Any, Dict

from avicena.util.Exceptions import InvalidConfigException


def _validate_db_details(db_config: Dict[str, Any]) -> bool:
    """
    Validate the database details in the app_config dictionary that has been loaded
    :param db_config: the child dictionary with database specific details
    """
    required_types = {'enabled': bool, 'url': str}
    for field in required_types:
        if field not in db_config:
            raise InvalidConfigException(f"app_config.database missing required field {field}")
        if type(db_config[field]) != required_types[field]:
            raise InvalidConfigException(
                f"app_config.database.{field} is expected to be {required_types[field]}, found {type(db_config[field])} instead")
    return db_config['enabled']


def validate_app_config(loaded_config: Dict[str, Any]) -> None:
    """
    Validate the overall app_config.yaml file.
    This validation raises Exceptions for name mismatches and type mismatches in the configuration file
    :param loaded_config: A dictionary loaded from the app_config.yaml
    """
    required_types = {'database': dict, 'geocoder_key': str, 'trips_parser': str, 'optimizer': str, 'seed': int}
    for field in required_types:
        if field not in loaded_config:
            raise InvalidConfigException(f"app_config missing required field {field}")
        if type(loaded_config[field]) != required_types[field]:
            raise InvalidConfigException(
                f"app_config.{field} is expected to be {required_types[field]}, found {type(loaded_config[field])} instead")
    db_enabled = _validate_db_details(loaded_config['database'])
    if not db_enabled:
        non_db_required_fields = {'merge_address_table_path': str, 'revenue_table_path': str, 'driver_table_path': str,
                                  'output_directory': str}
        for field in non_db_required_fields:
            if field not in loaded_config:
                raise InvalidConfigException(f"app_config missing required field {field}")
            if type(loaded_config[field]) != non_db_required_fields[field]:
                raise InvalidConfigException(
                    f"app_config.{field} is expected to be {non_db_required_fields[field]}, found {type(loaded_config[field])} instead")
