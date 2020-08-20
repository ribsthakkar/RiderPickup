import pandas as pd
from Driver import Driver
from Trip import Trip, TripType
from docplex.mp.model import Model

# Read input data
trip_df = pd.read_csv("Trips.csv")
driver_df = pd.read_csv("Drivers.csv")
# Preprocess input data
"""
1. Get all trip times/miles for each OD pair
"""
drivers = set()
locations = set()
driverLocations = set()

primary_trips = set()
secondary_trips = set()
location_pair = set()
inflow_trips = dict()
outlfow_trips = dict()
last_trip = None
count = 0
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
        if type == TripType.B and start == 0:  # Assuming that a B trip with no required pickup time will require pickup 1 hr after A trip dropoff
            start = last_trip.end + (1 / 24)
        cap = 1 if row['trip_los'] == 'A' else 1.5
        locations.add(o)
        locations.add(d)
        t = Trip(o, d, cap, id, type, start, end)
        primary_trips.add(t)
        location_pair.add((o, d))
        if o not in outlfow_trips:
            outlfow_trips[o] = {t}
        else:
            outlfow_trips[o].add(t)
        if d not in inflow_trips:
            inflow_trips[d] = {t}
        else:
            inflow_trips[d].add(t)
        count += 1
        last_trip = t
        if count == 2:
            break
id = 1

for index, row in driver_df.iterrows():
    cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
    drivers.add(Driver(row['ID'], row['Driver'], row['Address'], cap))
    locations.add(row['Address'])
    driverLocations.add(row['Address'])
    # for location in locations:
    #     t = Trip(row['Address'], location, cap, id, TripType.INTER,0.0, 1.0)
    #     secondary_trips.add(t)
    #     trip_dict[(row['Address'],location)] = t
    #     t = Trip(location, row['Address'], cap, id+1, TripType.INTER,0.0, 1.0)
    #     secondary_trips.add(t)
    #     trip_dict[(location, row['Address'])] = t
for o in locations:
    for d in locations:
        if o is not d and (o, d) not in location_pair:
            t = Trip(o, d, 0, id, TripType.INTER_A, 0.0, 1.0)
            if o not in outlfow_trips:
                outlfow_trips[o] = {t}
            else:
                outlfow_trips[o].add(t)
            if d not in inflow_trips:
                inflow_trips[d] = {t}
            else:
                inflow_trips[d].add(t)
            secondary_trips.add(t)
            id += 1

all_trips = []
all_trips += primary_trips
all_trips += secondary_trips
sorted(all_trips, key=lambda x: x.start)
print("Number of primary trips ", len(primary_trips))
print("Number of possible secondary trips", len(secondary_trips))
print("Total Number of possible trips", len(all_trips))
indices = {k: v for v, k in enumerate(all_trips)}
INT_VARS_OFFSET = len(all_trips) * len(drivers)
print("Total number of variables", INT_VARS_OFFSET * 2)
print("Driver details")
for i, driver in enumerate(drivers):
    print("Driver", i, driver.name)

print("Trip details")
for i, trip in enumerate(all_trips):
    if trip.type == TripType.A or trip.type == TripType.B:
        print("Primary trip", i, "FROM", trip.lp.o, "TO", trip.lp.d, "pickup by", trip.start, "drop off by", trip.end)
    else:
        print("Secondary trip", i, "FROM", trip.lp.o, "TO", trip.lp.d, "pickup by", trip.start, "drop off by", trip.end)

print("Locataion details")
for i, loc in enumerate(locations):
    print("Location", i, loc)

# Formulate optimization problem
"""
For each driver
For each location
"""
mdl = Model(name="Patient Transport")
x = []

for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        x.append(mdl.binary_var(name='y' + '_' + str(i) + '_' + str(j)))

for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        x.append(mdl.continuous_var(lb=0, ub=1, name='t' + '_' + str(i) + '_' + str(j)))

print("Number of variables: ", mdl.number_of_variables)

# Inflow = outflow for all locations
for loc in locations:
    for i, d in enumerate(drivers):
        total = 0.0
        for intrip in inflow_trips[loc]:
            total += x[i * len(all_trips) + indices[intrip]]
        for otrip in outlfow_trips[loc]:
            total -= x[i * len(all_trips) + indices[otrip]]
        mdl.add_constraint(ct=total == 0, ctname='flowinout' + '_' + str(hash(loc))[:5] + '_' + str(i))
print("Number of constraints after flow in = flow out", mdl.number_of_constraints)

# Inflow before outflow for all locations except driver home --- can't figure this out ----
for loc in locations:
    for i, d in enumerate(drivers):
        for intrip in inflow_trips[loc]:
            total = 0.0
            for otrip in outlfow_trips[loc]:
                total += (x[INT_VARS_OFFSET + i * len(all_trips) + indices[intrip]] + intrip.lp.time) - x[
                    INT_VARS_OFFSET + i * len(all_trips) + indices[otrip]]
            if loc in driverLocations:  # leave home before coming back
                mdl.add_constraint(ct=total >= 0, ctname='outb4in' + '_' + str(hash(loc))[:5] + '_' + str(i))
            else:
                mdl.add_constraint(ct=total <= 0, ctname='inb4out' + '_' + str(hash(loc))[:5] + '_' + str(i))
print("Number of constraints after flow in before flow out", mdl.number_of_constraints)
# Only one driver per trip
for j, trip in enumerate(all_trips):
    total = 0
    for i, driver in enumerate(drivers):
        total += x[i * len(all_trips) + j]
    if j < len(primary_trips):
        mdl.add_constraint(ct=total == 1, ctname='primaryTrip' + '_' + str(j))
    else:
        mdl.add_constraint(ct=total <= 1, ctname='secondaryTrip' + '_' + str(j))
print("Number of constraints after required trips", mdl.number_of_constraints)

# Trips can't overlap for a driver
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        for k, trip2 in enumerate(all_trips[j + 1:]):
            l = k + j
            if trip.start + trip.lp.time >= trip2.start - 0.01041666666:
                total = ((x[i * len(all_trips) + l] * x[INT_VARS_OFFSET + i * len(all_trips) + l] - x[
                    i * len(all_trips) + j] * x[INT_VARS_OFFSET + i * len(all_trips) + j])
                         + (x[i * len(all_trips) + j] * (x[INT_VARS_OFFSET + i * len(all_trips) + j] + trip.lp.time) -
                            x[i * len(all_trips) + l] * x[INT_VARS_OFFSET + i * len(all_trips) + l]) - trip.lp.time)
                mdl.add_constraint(ct=total <= 0, ctname='tripConflict' + '_' + str(i) + '_' + str(j) + '_' + str(l))
            else:
                break
print("Number of constraints after overlap constraints", mdl.number_of_constraints)

# Trips can't overlap for a driver
# for i, driver in enumerate(drivers):
#     for j, trip in enumerate(all_trips):
#         for k, trip2 in enumerate(all_trips):
#             if trip is not trip2:
#                 total = ((x[INT_VARS_OFFSET + i * len(all_trips) + k] - x[INT_VARS_OFFSET + i * len(all_trips) + j])
#                          + ((x[INT_VARS_OFFSET + i * len(all_trips) + j] + trip.lp.time) -
#                             x[INT_VARS_OFFSET + i * len(all_trips) + k]) - trip.lp.time)
#                 mdl.add_constraint(ct= total <= 0, ctname='tripConflict'+'_'  + str(i) +'_' + str(j)+'_'  + str(k))
# Wheelchair constraint
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        total = (x[i * len(all_trips) + j] * trip.space - driver.capacity)
        mdl.add_constraint(ct=total <= 0, ctname='capacity' + '_' + str(i) + '_' + str(j))
print("Number of constraints after wheelchair capacity", mdl.number_of_constraints)

# Pickup at most 15 mins before for primary trips
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        if trip in primary_trips:
            total = ((trip.start - 0.01041666666) - x[INT_VARS_OFFSET + i * len(all_trips) + j])
            mdl.add_constraint(ct=total <= 0, ctname='pickup' + '_' + str(i) + '_' + str(j))
print("Number of constraints after pickup time constraint", mdl.number_of_constraints)

# Dropoff by the required time for primary trips
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        if trip in primary_trips:
            total = ((x[INT_VARS_OFFSET + i * len(all_trips) + j] + trip.lp.time) - trip.end)
            mdl.add_constraint(ct=total <= 0, ctname='dropoff' + '_' + str(i) + '_' + str(j))

print("Number of constraints after dropoff time constraint", mdl.number_of_constraints)

total = 0.0
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        total += trip.lp.time * x[i * len(all_trips) + j]

print(mdl.get_constraint_by_name("pickup_0_1"))

print('\n'.join(str(c) for c in mdl.iter_constraints()))

mdl.minimize(total)
mdl.solve()
print("Solve status: " + str(mdl.get_solve_status()))
print("Obj value: " + str(mdl.objective_value))

for var in x:
    print(var.get_name() + ": " + str(var.solution_value))

with open("modeltrips.txt", "w+") as o:
    o.write("Trip_id, start, end, pickup, dropoff\n")
    for i, trip in enumerate(all_trips):
        o.write(str(trip.id) + "," + str(trip.lp.o) + "," + str(trip.lp.d) + "," + str(trip.start) + "," + str(
            trip.end) + "\n")

with open("modelsoln.txt", "w+") as o:
    o.write("Driver_id, Trip_id, Time\n")
    for i, driver in enumerate(drivers):
        for j, trip in enumerate(all_trips):
            if x[i * len(all_trips) + j].solution_value == 1:
                o.write(driver.name + "," + str(trip.id) + "," + str(
                    x[INT_VARS_OFFSET + i * len(all_trips) + j].solution_value) + "\n")
                print("Driver ", driver.name, " goes from ", trip.lp.o, " to ", trip.lp.d, " at ",
                      x[INT_VARS_OFFSET + i * len(all_trips) + j].solution_value)
