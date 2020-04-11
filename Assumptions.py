from constants import FIFTEEN

preprocess_assumptions = {
 "UNKNOWN_TIME_BUFFER": FIFTEEN * 10,
 "UNKNOWN_TIME_DROP": FIFTEEN * 8,
 "MERGE_ADDRESSES": {"1631 E 2nd St", "1110 W Willia"},
 "MERGE_ADDRESS_WINDOW": FIFTEEN

}

opt_params = {
   "TRIPS_TO_DO": 53, # if greater than total number of trips, then ignored
    "DRIVER_IDX": 1, # index of which driver's address is assumed to be debot

    "MIN_DRIVERS": 4,
    "MAX_DRIVERS": 4, # unsued
    "DRIVER_PEN": 10000,

    "MAX_WHEELCHAIR_DRIVERS": 2,
    "W_DRIVER_PEN": 30000,

    "PICKUP_WINDOW": FIFTEEN/2, # general window unused
    "EARLY_PICKUP_WINDOW": FIFTEEN * 2,
    "LATE_PICKUP_WINDOW": FIFTEEN * 3,
    "DROP_WINDOW": FIFTEEN * 2/3, #general window unused
    "EARLY_DROP_WINDOW": FIFTEEN * 4,
    "LATE_DROP_WINDOW": FIFTEEN * 2/3,

    "DRIVER_CAP": 2.5, # W trips take 1.5 space and A trips take 1 space

    "ROUTE_LIMIT": FIFTEEN * 60,

    "MERGE_PENALTY": 1000,


    "REVENUE_PENALTY": 50,
    # "MIN_DRIVING_SPEED": 40, # unused, not working
    # "MAX_DRIVING_SPEED": 60, # unused, not working
    # "SPEED_PENALTY" : 100, # Penalty is applied to inverse of speed unused, not working

    "TIME_LIMIT": 900,
    "MIP_GAP": 0.03,
    "MODEL_NAME": "PDWTW",
}