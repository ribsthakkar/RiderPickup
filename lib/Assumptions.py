from .constants import FIFTEEN

preprocess_assumptions = {
 "UNKNOWN_TIME_BUFFER": FIFTEEN * 10,
 "UNKNOWN_TIME_DROP": FIFTEEN * 8,
 "MERGE_ADDRESSES": {"1631 E 2nd St", "1110 W Willia", "1801 E 51st St , Austin , TX", "1000 E 41st St"},
 "MERGE_ADDRESS_WINDOW": FIFTEEN

}

opt_params = {
   "TRIPS_TO_DO": 53, # if greater than total number of trips, then ignored
    "DRIVER_IDX": 1, # index of which driver's address is assumed to be debot

    "NUM_DRIVERS": 4,
    "MIN_DRIVERS": 4,
    "MAX_DRIVERS": 60, # unused
    "DRIVER_PEN": 10000,

    "MAX_WHEELCHAIR_DRIVERS": 2,
    "MIN_WHEELCHAIR_DRIVERS": 2,
    "W_DRIVER_PEN": 3000,

    "PICKUP_WINDOW": FIFTEEN/2, # general window unused
    "EARLY_PICKUP_WINDOW": FIFTEEN * 3,
    "LATE_PICKUP_WINDOW": FIFTEEN * 3,
    "DROP_WINDOW": FIFTEEN * 2/3, #general window unused
    "EARLY_DROP_WINDOW": FIFTEEN * 4,
    "LATE_DROP_WINDOW": FIFTEEN * 1/3,

    "DRIVER_CAP": 2.5, # W trips take 1.5 space and A trips take 1 space

    "ROUTE_LIMIT": FIFTEEN * 60,  # Limits on the length of time of the route

    "MERGE_PENALTY": 1000,  # Penalty for not meeting AB or BC Trip Merge Requirements


    "REVENUE_PENALTY": 250,
    # "MIN_DRIVING_SPEED": 40, # unused, not working
    # "MAX_DRIVING_SPEED": 60, # unused, not working
    # "SPEED_PENALTY" : 100, # Penalty is applied to inverse of speed unused, not working

    "TIME_LIMIT": 900 * 4 * 8, # Overall Solver time limit in seconds
    "MIP_GAP": 0.03,  # Solver Gap Levels
    "MODEL_NAME": "PDWTW",

    # Generalized Optimizer params
    "STAGE1_TIME": 900,
    "STAGE1_GAP": 0.05,
    "STAGE2_TIME": 900,
    "STAGE2_GAP": 0.05
}

gen_opt_params = {
   "TRIPS_TO_DO": 1000, # if greater than total number of trips, then ignored

    "NUM_DRIVERS": 4,

    "EARLY_PICKUP_WINDOW": FIFTEEN * 3,
    "LATE_PICKUP_WINDOW": FIFTEEN,
    "EARLY_DROP_WINDOW": FIFTEEN * 4,
    "LATE_DROP_WINDOW": FIFTEEN * 1/3,

    "DRIVER_CAP": 2.5, # W trips take 1.5 space and A trips take 1 space

    "ROUTE_LIMIT": FIFTEEN * 60,  # Limits on the length of time of the route
    "ROUTE_LIMIT_PENALTY": 500,  # Limits on the length of time of the route
    "EARLY_DAY_TIME": FIFTEEN * 18,  # Limits on the length of time of the route

    "MERGE_PENALTY": 1000,  # Penalty for not meeting AB or BC Trip Merge Requirements


    "REVENUE_PENALTY": 250, # Unused at the moment
    "MODEL_NAME": "PDWTW",

    "STAGE1_TIME": 120, # Stage 1 Time
    "STAGE1_GAP": 0.05, # Stage 1 Target MIP Gap
    "STAGE2_TIME": 120, # Stage 2 Time
    "STAGE2_GAP": 0.05 # Stage 2 Target MIP Gap
}