import argparse

import yaml

from avicena.util.Database import close_db_session, create_db_session, save_to_db_session, commit_db_session
from avicena.models.Driver import load_drivers_from_csv
from avicena.models.MergeAddress import load_merge_details_from_csv
from avicena.models.RevenueRate import load_revenue_table_from_csv
from avicena.util.ConfigValidation import _validate_db_details
from avicena.util.Exceptions import InvalidConfigException

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Populate Database with Base Information needed including Revenue Table, Merge Address Details, and Driver Details.')

    parser.add_argument('-c', '--app-config', action='store', type=str, dest='app_config', default='config/app_config.yaml',
                        help='Path to application config file')

    parser.add_argument('-r', '--revenue-table-csv', action='store', type=str, dest='revenue_table_file',
                        help='Path to revenue table CSV')

    parser.add_argument('-m', '--merge-details-csv', action='store', type=str, dest='merge_details_file',
                        help='Path to merge details CSV')

    parser.add_argument('-d', '--driver-details-csv', action='store', type=str, dest='driver_details_file',
                        help='Path to driver details CSV')

    args = parser.parse_args()
    with open(args.app_config) as cfg_file:
        app_config = yaml.load(cfg_file)
    if 'database' not in app_config:
        raise InvalidConfigException("Missing database input config yaml")
    _validate_db_details(app_config['database'])

    db_session = create_db_session(app_config['database'])
    rev_table = load_revenue_table_from_csv(args.revenue_table_file)
    for level_of_service in rev_table:
        for rate in rev_table[level_of_service]:
            save_to_db_session(db_session, rate)

    merge_details = load_merge_details_from_csv(args.merge_details_file)
    for merge_address in merge_details.values():
        save_to_db_session(db_session, merge_address)

    drivers = load_drivers_from_csv(args.driver_details_file)
    for driver in drivers:
        save_to_db_session(db_session, drivers)

    commit_db_session(db_session)
    close_db_session(db_session)