import pandas as pd
from Driver import Driver
from Trip import Trip, TripType
import pyOpt


exit(1)
# Read input data
trip_df = pd.read_csv("Trips.csv")
driver_df = pd.read_csv("Drivers.csv")
# Preprocess input data
"""
1. Get all trip times/miles for each OD pair
"""
drivers = set()
locations = set()

primary_trips = set()
secondary_trips = set()
all_trips = set()


for index, row in trip_df.iterrows():
    if not row['trip_status'] == "CANCELLED":
        o = row['scrub_trip_pickup_address']
        d = row['scrub_trip_dropoff_address']
        start = float(row['trip_pickup_time'])
        end = float(row['trip_dropoff_time'])
        if end == 0.0:
            end = 1.0
        id = row['trip_id']
        type = TripType.A if 'A' in id else TripType.B
        cap = 1 if row['trip_los'] == 'A' else 1.5
        locations.add(o)
        locations.add(d)
        primary_trips.add(Trip(o, d, cap, id, type, start, end))
id = 1

for index, row in driver_df.iterrows():
    cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
    drivers.add(Driver(row['Driver'], row['Address'], cap))
    for location in locations:
        secondary_trips.add(Trip(row['Address'], location, cap, id, TripType.INTER,0.0, 1.0))
        secondary_trips.add(Trip(location, row['Address'], cap, id+1, TripType.INTER,0.0, 1.0))
    locations.add(row['Address'])
    id += 2

all_trips = []
all_trips += primary_trips
all_trips += secondary_trips
print("Number of primary trips ", len(primary_trips))
print("Number of possible secondary trips", len(secondary_trips))
print("Total Number of possible trips", len(all_trips))

# Formulate optimization problem
"""
For each driver
For each location
"""
def objfunc(x):
    total = 0.0
    fail = 0
    INT_VARS_OFFSET = len(all_trips) * len(drivers)
    for i, driver in enumerate(drivers):
        for j, trip in enumerate(all_trips):
            total += trip.lp.time * x[i * len(all_trips) + j]

    constraints = []

    # Each trip only has one driver
    for j, trip in enumerate(all_trips):
        total = 0
        for i, driver in enumerate(drivers):
            total += x[i * len(all_trips) + j]
        constraints.append(total)

    # Trips do not overlap for each driver
    for i, driver in enumerate(drivers):
        for j, trip in enumerate(all_trips):
            for k, trip2 in enumerate(all_trips):
                if trip is not trip2:
                    constraints.append((x[i * len(all_trips) + k]*x[INT_VARS_OFFSET+i * len(all_trips) + k]-x[i * len(all_trips) + j]*x[INT_VARS_OFFSET+i * len(all_trips) + j])
                                       + (x[i * len(all_trips) + j] *(x[INT_VARS_OFFSET+i * len(all_trips) + j]+trip.lp.time) - x[i * len(all_trips) + k]*x[INT_VARS_OFFSET+i * len(all_trips) + k]) - trip.lp.time)

    # Wheelchair constraint
    for i, driver in enumerate(drivers):
        for j, trip in enumerate(all_trips):
            constraints.append(x[i * len(all_trips) + j]*trip.space - driver.capacity)

    # Pickup at most 15 mins before
    for i, driver in enumerate(drivers):
        for j, trip in enumerate(all_trips):
            constraints.append(x[i * len(all_trips) + j] * (trip.start  - 0.01041666666) - x[i * len(all_trips) + j]* x[INT_VARS_OFFSET + i * len(all_trips) + j])

    # Dropoff by the required time
    for i, driver in enumerate(drivers):
        for j, trip in enumerate(all_trips):
            constraints.append(x[i * len(all_trips) + j] * (x[INT_VARS_OFFSET + i * len(all_trips) + j] + trip.lp.time) - x[i * len(all_trips) + j] * trip.end)

    return total, constraints, fail
# Solve Optimization Problem
opt_prob = pyOpt.Optimization('TP37 Constrained Problem',objfunc)
opt_prob.addObj('Time Traveled')
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        opt_prob.addVar('y' + str(i) + str(j), 'i', lower=0, upper=1)
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        opt_prob.addVar('t' + str(i) + str(j), 'c', lower=0, upper=1)
for j, trip in enumerate(all_trips):
    total = 0
    if j < len(primary_trips):
        opt_prob.addCon('primaryTrip' + str(j), 'e')
    else:
        opt_prob.addCon('secondaryTrip' + str(j), 'i')
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        for k, trip2 in enumerate(all_trips):
            if trip is not trip2:
                opt_prob.addCon('tripConflict' + str(i) + str(j) + str(k), 'i')
# Wheelchair constraint
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        opt_prob.addCon('capacity'+str(i)+str(j), 'i')

# Pickup at most 15 mins before
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        opt_prob.addCon('pickup' + str(i) + str(j), 'i')
# Dropoff by the required time
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        opt_prob.addCon('dropoff'+str(i) + str(j), 'i')