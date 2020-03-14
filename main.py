from PDWTWOptimizer import PDWTWOptimizer
from Solver import TripCalculator
from datetime import datetime
from constants import FIFTEEN

tc = TripCalculator("../Data/in_trips.csv", "../Data/in_drivers.csv")

opt_params = {
   "TRIPS_TO_DO": 53,
    "DRIVER_IDX": 1,
    "NUM_DRIVERS": 4,
    "PICKUP_WINDOW": FIFTEEN/2,
    "DROP_WINDOW": FIFTEEN * 2/3,
    "DRIVER_CAP": 2,
    "TIME_LIMIT": 900,
    "MIP_GAP": 0.01,
    "MODEL_NAME": "PDTWT"
}
optimizer = tc.prepare_model(PDWTWOptimizer, opt_params)
outfile = 'output/pdwtw_final_output' + str(datetime.now()) + '.csv'
tc.solve(outfile)
tc.visualize(outfile, False)
