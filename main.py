from PDWTWOptimizer import PDWTWOptimizer
from Solver import TripPreprocess as tp
from datetime import datetime
from constants import FIFTEEN

assumptions = {
 "UNKNOWN_TIME_BUFFER": FIFTEEN * 10,
 "MERGE_ADDRESSES": {"1631 E 2nd St", "1110 W Willia"},
 "MERGE_ADDRESS_WINDOW": FIFTEEN

}
#rev_table = tp.load_revenue_table('../Data/rev_table.csv')
#trips = tp.prepare_and_load_trips('../Data/in_trips.csv',rev_table, assumptions)
trips = tp.load_trips('calc_trips.csv')
drivers = tp.load_drivers('../Data/in_drivers.csv')


opt_params = {
   "TRIPS_TO_DO": 53,
    "DRIVER_IDX": 1,
    "NUM_DRIVERS": 4,
    "PICKUP_WINDOW": FIFTEEN/2,
    "DROP_WINDOW": FIFTEEN * 2/3,
    "DRIVER_CAP": 2,
    "TIME_LIMIT": 1500,
    "MIP_GAP": 0.01,
    "MODEL_NAME": "PDTWT"
}
optimizer = PDWTWOptimizer(trips, drivers, opt_params)
outfile = 'output/pdwtw_final_output' + str(datetime.now()) + '.csv'
optimizer.solve(outfile)
optimizer.visualize(outfile, False)
