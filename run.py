from GeneralizedOptimizer import GeneralOptimizer
from Preprocessor import TripPreprocess as tp
from datetime import datetime
from Assumptions import preprocess_assumptions, gen_opt_params
from constants import keys, SPEED

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the Generalized Optimizer with given files')
    rn = parser.add_argument_group('required named args')

    parser.add_argument('-s', '--speed', action='store', type=int, dest='s', default=60,
                    help='Speed in MPH to use for time calculations. Default is 60 MPH')

    rn.add_argument('-r', '--rev', action='store', type=str, dest='r',
                        help='Path to CSV with Revenue Table', required=True)
    rn.add_argument('-t','--trips', action='store', type=str, dest='t',
                        help='Path to CSV Trips File', required=True)
    rn.add_argument('-d', '--drivers', action='store', type=str, dest='d',
                        help='Path to CSV Driver Details File', required=True)
    rn.add_argument('-k', '--key', action='store', type=str, dest='k',
                        help='Path to File With OpenCage GeoCode API Key', required=True)
    rn.add_argument('-o', '--output', action='store', type=str, dest='o',
                        help='File To Store Assignment CSV', required=True)
    rn.add_argument('-v', '--vis', action='store', type=str, dest='v',
                        help='File To Store Assignment HTML Visualization', required=True)

    args = parser.parse_args()
    if not all([args.r, args.k, args.t, args.d, args.o, args.v]):
        parser.error("Missing one or more arguments")
    SPEED = args.s

    print("Revenue Table", args.r)
    print("Trips File", args.t)
    print("Drivers File", args.d)
    print("Assumed Driving Speed", args.s)
    keyFile = open(args.k)
    keys['geo_key'] = keyFile.readline().rstrip()
    rev_table = tp.load_revenue_table(args.r)
    trips = tp.prepare_and_load_trips(args.t, rev_table, preprocess_assumptions)
    drivers = tp.load_drivers(args.d)
    optimizer = GeneralOptimizer(trips, drivers, gen_opt_params)
    outfile = args.o
    optimizer.solve(outfile)
    optimizer.visualize(outfile, args.v)