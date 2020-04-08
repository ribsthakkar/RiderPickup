from PDWTWOptimizer import PDWTWOptimizer
from Solver import TripPreprocess as tp
from datetime import datetime
from constants import FIFTEEN

assumptions = {
 "UNKNOWN_TIME_BUFFER": FIFTEEN * 10,
 "UNKNOWN_TIME_DROP": FIFTEEN * 8,
 "MERGE_ADDRESSES": {"1631 E 2nd St", "1110 W Willia"},
 "MERGE_ADDRESS_WINDOW": FIFTEEN

}

opt_params = {
   "TRIPS_TO_DO": 53,
    "DRIVER_IDX": 1,
    "NUM_DRIVERS": 4,
    "PICKUP_WINDOW": FIFTEEN/2,
    "DROP_WINDOW": FIFTEEN * 2/3,
    "DRIVER_CAP": 2,
    "ROUTE_LIMIT": FIFTEEN * 60,
    "MERGE_PENALTY": 1000,
    "MIN_DRIVING_SPEED": 40,
    "MAX_DRIVING_SPEED": 60,
    "TIME_LIMIT": 3600,
    "MIP_GAP": 0.03,
    "MODEL_NAME": "PDTWT",
}
rev_table = tp.load_revenue_table('../Data/rev_table.csv')
trips = tp.prepare_and_load_trips('../Data/in_trips_010220.csv',rev_table, assumptions)
# trips = tp.load_trips('calc_trips.csv')
drivers = tp.load_drivers('../Data/in_drivers.csv')
# optimizer = PDWTWOptimizer(trips, drivers, opt_params)
# outfile = 'output/pdwtw_final_output' + str(datetime.now()) + '.csv'
# optimizer.solve(outfile)
# optimizer.visualize(outfile, 'vis-010220.html')

trips2 = tp.prepare_and_load_trips('../Data/in_trips_022620.csv',rev_table, assumptions)
optimizer2 = PDWTWOptimizer(trips2, drivers, opt_params)
outfile = 'output/pdwtw_final_output' + str(datetime.now()) + '.csv'
optimizer2.solve(outfile)
optimizer2.visualize(outfile, 'vis-022620.html')
