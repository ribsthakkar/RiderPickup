from datetime import datetime

import pandas as pd
from Driver import Driver
from Trip import Trip, TripType
from docplex.mp.model import Model


def f(driver):
    def filt(trip):
        return not (trip.lp.o in driverLocations and trip.lp.o != driver.address) or (
                trip.lp.d in driverLocations and trip.lp.d != driver.address)

    return filt


print("Started", datetime.now())
t = datetime.now()
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
driver_home_trips = set()
secondary_trips = set()
location_pair = set()
homes = set()
not_homes = set()
inflow_trips = dict()
outlfow_trips = dict()
TRIPS_TO_DO = 10
NUM_DRIVERS = 2
FIFTEEN = 0.01041666666
THIRTY = FIFTEEN * 2
TWENTY = FIFTEEN * (4 / 3)
TEN = FIFTEEN * (2 / 3)
FIVE = FIFTEEN * (1 / 3)

last_trip = None
count = 0
for index, row in trip_df.iterrows():
    if not row['trip_status'] == "CANCELED":
        o = row['scrub_trip_pickup_address']
        d = row['scrub_trip_dropoff_address']
        start = float(row['trip_pickup_time'])
        end = float(row['trip_dropoff_time'])
        if end == 0.0:
            end = 1.0
        id = row['trip_id']
        if 'A' in id:
            type = TripType.B
            homes.add(o)
            not_homes.add(d)
        else:
            type = TripType.D
        if type == TripType.D and start == 0:
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
        if count == TRIPS_TO_DO:
            break
id = 1

count = 0
for index, row in driver_df.iterrows():
    cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
    drivers.add(Driver(row['ID'], row['Driver'], row['Address'], cap))
    locations.add(row['Address'])
    driverLocations.add(row['Address'])
    count += 1
    if count == NUM_DRIVERS:
        break

for o in locations:
    for d in locations:
        if o != d and (o, d) not in location_pair:
            if o in driverLocations and d in driverLocations:
                continue
            if o in driverLocations:
                t = Trip(o, d, 0, id, TripType.INTER_A, 0.0, 1.0)
                if o not in outlfow_trips:
                    outlfow_trips[o] = {t}
                else:
                    outlfow_trips[o].add(t)
                if d not in inflow_trips:
                    inflow_trips[d] = {t}
                else:
                    inflow_trips[d].add(t)
                driver_home_trips.add(t)
                id += 1
            elif d in driverLocations:
                t = Trip(o, d, 0, id, TripType.INTER_B, 0.0, 1.0)
                if o not in outlfow_trips:
                    outlfow_trips[o] = {t}
                else:
                    outlfow_trips[o].add(t)
                if d not in inflow_trips:
                    inflow_trips[d] = {t}
                else:
                    inflow_trips[d].add(t)
                driver_home_trips.add(t)
                id += 1
            elif d in homes:
                t = Trip(o, d, 0, id, TripType.A, 0.0, 1.0)
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
            elif d in not_homes:
                t = Trip(o, d, 0, id, TripType.C, 0.0, 1.0)
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
all_trips += driver_home_trips
print("Number of primary trips ", len(primary_trips))
print("Number of possible secondary trips", len(secondary_trips))
print("Total Number of possible trips", len(all_trips))
print("Driver details")
for i, driver in enumerate(drivers):
    print("Driver", i, driver.name)

print("Trip details")
for i, trip in enumerate(all_trips):
    if trip.type == TripType.B or trip.type == TripType.D:
        print("Primary trip", i, "FROM", trip.lp.o, "TO", trip.lp.d, "pickup by", trip.start, "drop off by", trip.end)
    elif trip.type == TripType.INTER_A or trip.type == TripType.INTER_B:
        print("Driver Home trip", i, "FROM", trip.lp.o, "TO", trip.lp.d, "pickup by", trip.start, "drop off by",
              trip.end)
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

valid_trips = 0
for i, driver in enumerate(drivers):
    for j, trip in enumerate(filter(f(driver), all_trips)):
        x.append(mdl.binary_var(name='y' + '_' + str(i) + '_' + str(j)))
        valid_trips += 1

for i, driver in enumerate(drivers):
    for j, trip in enumerate(filter(f(driver), all_trips)):
        x.append(mdl.continuous_var(lb=0, ub=1, name='t' + '_' + str(i) + '_' + str(j)))

indices = {driver: {k: v for v, k in enumerate(filter(f(driver), all_trips))} for driver in drivers}
for k, v in indices.items():
    print(k, ":", v)
print(valid_trips, len(drivers))
print(len(x))
print(x)

valid_trips //= len(drivers)
INT_VARS_OFFSET = len(x) // 2

print("Number of variables: ", mdl.number_of_variables)

# Inflow = outflow for all locations
for i, d in enumerate(drivers):
    for loc in locations:
        if loc in driverLocations and loc != d.address:
            continue
        total = 0.0
        for intrip in inflow_trips[loc]:
            if (intrip.lp.o in driverLocations and intrip.lp.o != d.address): continue
            total += x[i * valid_trips + indices[d][intrip]]
        for otrip in outlfow_trips[loc]:
            if (otrip.lp.d in driverLocations and otrip.lp.d != d.address): continue
            total -= x[i * valid_trips + indices[d][otrip]]
        mdl.add_constraint(ct=total == 0, ctname='flowinout' + '_' + str(loc)[:5] + '_' + str(i))
print("Number of constraints after flow in = flow out", mdl.number_of_constraints)

home_type_conflicts = {(TripType.INTER_A, TripType.B), (TripType.INTER_A, TripType.INTER_B),
                       (TripType.A, TripType.B),
                       (TripType.D, TripType.C), (TripType.D, TripType.A), (TripType.D, TripType.INTER_B)}
not_homes_type_conflicts = {(TripType.INTER_A, TripType.A), (TripType.INTER_A, TripType.D),
                            (TripType.INTER_A, TripType.INTER_B),
                            (TripType.C, TripType.D),
                            (TripType.B, TripType.A), (TripType.B, TripType.C), (TripType.B, TripType.INTER_B)}
driver_type_conflicts = {(TripType.INTER_A, TripType.INTER_B)}
# Inflow before outflow for all locations except driver home --- can't figure this out ----
for i, d in enumerate(drivers):
    for loc in locations:
        if loc in driverLocations and loc != d.address:
            continue
        if loc in homes:
            type_conflicts = home_type_conflicts
            # If outgoing trip A == 1, sum of all Ds must be >= 1 for all A trips
            # If outgoing trip B == 1 , sum of As/Inter_As must be >= 1 for all B trips
            # If outgoing trip C == 1, sum of Ds must be >= 1 for all C trips
            # If outgoing trip I_B == 1, sum of Inter_A and Ds must be >= 1 for all I_B trips
            for otrip in outlfow_trips[loc]:
                if (otrip.lp.d in driverLocations and otrip.lp.d != d.address): continue
                Dsum = 0.0
                Asum = 0.0
                IAsum = 0.0
                for intrip in inflow_trips[loc]:
                    if (intrip.lp.o in driverLocations and intrip.lp.o != d.address): continue
                    if intrip.type == TripType.A:
                        Asum += x[i * valid_trips + indices[d][intrip]]
                    elif intrip.type == TripType.INTER_A:
                        IAsum += x[i * valid_trips + indices[d][intrip]]
                    elif intrip.type == TripType.D:
                        Dsum += x[i * valid_trips + indices[d][intrip]]
                    else:
                        print("Something not sure???????")
                if otrip.type == TripType.A:
                    mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][otrip]] == 1, then_ct=Dsum >= 1)
                if otrip.type == TripType.B:
                    mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][otrip]] == 1, then_ct=Asum + IAsum >= 1)
                if otrip.type == TripType.C:
                    mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][otrip]] == 1, then_ct=Dsum >= 1)
                if otrip.type == TripType.INTER_B:
                    mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][otrip]] == 1, then_ct=IAsum + Dsum >= 1)

        elif loc in not_homes:
            type_conflicts = not_homes_type_conflicts
            # If outgoing trip A == 1, sum of all Bs must be >= 1
            # If outgoing trip C == 1, sum of all Bs must be >= 1
            # If outgoing trip D == 1, sum of Inter_As/B/Cs must be >= 1
            # If outgoing trip I_B == 1, sum of Inter_A and Bs must be >= 1
            for otrip in outlfow_trips[loc]:
                if (otrip.lp.d in driverLocations and otrip.lp.d != d.address): continue
                Bsum = 0.0
                Csum = 0.0
                IAsum = 0.0
                for intrip in inflow_trips[loc]:
                    if (intrip.lp.o in driverLocations and intrip.lp.o != d.address): continue
                    if intrip.type == TripType.B:
                        Bsum += x[i * valid_trips + indices[d][intrip]]
                    elif intrip.type == TripType.INTER_A:
                        IAsum += x[i * valid_trips + indices[d][intrip]]
                    elif intrip.type == TripType.C:
                        Csum += x[i * valid_trips + indices[d][intrip]]
                    else:
                        print("Something not sure???????")
                if otrip.type == TripType.A:
                    mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][otrip]] == 1, then_ct=Bsum >= 1)
                if otrip.type == TripType.C:
                    mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][otrip]] == 1, then_ct=Bsum >= 1)
                if otrip.type == TripType.D:
                    mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][otrip]] == 1, then_ct=IAsum + Csum + Bsum >= 1)
                if otrip.type == TripType.INTER_B:
                    mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][otrip]] == 1, then_ct=IAsum + Bsum >= 1)
        else:
            type_conflicts = driver_type_conflicts
        for intrip in inflow_trips[loc]:
            if (intrip.lp.o in driverLocations and intrip.lp.o != d.address): continue
            for otrip in outlfow_trips[loc]:
                if (otrip.lp.d in driverLocations and otrip.lp.d != d.address): continue
                if loc not in driverLocations:
                    if (intrip.type, otrip.type) in type_conflicts:
                        print("Intrip:", intrip.lp.o, intrip.lp.d, intrip.start, intrip.end, intrip.type)
                        print("Otrip:", otrip.lp.o, otrip.lp.d, otrip.start, otrip.end, otrip.type)
                        if loc in homes:
                            mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][intrip]] + x[
                                i * valid_trips + indices[d][otrip]] == 2, then_ct=x[INT_VARS_OFFSET + i * valid_trips +
                                                                                     indices[d][
                                                                                         intrip]] + intrip.lp.time + 0 <=
                                                                                   x[
                                                                                       INT_VARS_OFFSET + i * valid_trips +
                                                                                       indices[d][otrip]])
                        else:
                            mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][intrip]] + x[
                                i * valid_trips + indices[d][otrip]] == 2, then_ct=x[INT_VARS_OFFSET + i * valid_trips +
                                                                                     indices[d][
                                                                                         intrip]] + intrip.lp.time <= x[
                                                                                       INT_VARS_OFFSET + i * valid_trips +
                                                                                       indices[d][otrip]])
                        # mdl.add_constraint(ct=(x[INT_VARS_OFFSET + i * valid_trips + indices[d][intrip]] + intrip.lp.time -x[INT_VARS_OFFSET + i * valid_trips + indices[d][otrip]]) <= 0, ctname='tripord' + '_' + str(i) + '_' + str(intrip.id) + '_' + str(otrip.id))
                        # mdl.add_constraint(ct=x[i * valid_trips + indices[d][intrip]] >= x[i * valid_trips + indices[d][otrip]], ctname='tripordbool' + '_' + str(i) + '_' + str(intrip.id) + '_' + str(otrip.id))
                        # mdl.add_constraint(ct=x[i * valid_trips + indices[d][otrip]]* (x[INT_VARS_OFFSET + i * valid_trips + indices[d][intrip]] + intrip.lp.time) <= x[i * valid_trips + indices[d][intrip]] * x[INT_VARS_OFFSET + i * valid_trips + indices[d][otrip]], ctname='tripord' + '_' + str(i) + '_' + str(intrip.id) + '_' + str(otrip.id))
                        # mdl.add_if_then(if_ct=x[i * valid_trips + indices[d][intrip]] >= x[i * valid_trips + indices[d][otrip]], then_ct=x[INT_VARS_OFFSET + i * valid_trips + indices[d][intrip]] + intrip.lp.time <= x[INT_VARS_OFFSET + i * valid_trips + indices[d][otrip]])

print("Number of constraints after flow in before flow out", mdl.number_of_constraints)

# Only one driver per trip
for j, trip in enumerate(all_trips[:len(primary_trips) + len(secondary_trips)]):
    if trip.type != TripType.INTER_B and trip.type != TripType.INTER_A:
        total = 0
        for i, driver in enumerate(drivers):
            if (trip.lp.o in driverLocations and trip.lp.o != driver.address) or (
                    trip.lp.d in driverLocations and trip.lp.d != driver.address): continue
            total += x[i * valid_trips + j]
        if j < len(primary_trips):
            mdl.add_constraint(ct=total == 1, ctname='primaryTrip' + '_' + str(j))
print("Number of constraints after primary/secondary trips", mdl.number_of_constraints)

for i, driver in enumerate(drivers):
    total_o = 0.0
    total_d = 0.0
    total_n = 0.0
    for trip in filter(f(driver), (all_trips[len(primary_trips) + len(secondary_trips):])):
        j = indices[driver][trip]
        if trip.lp.o == driver.address:
            total_o += x[i * valid_trips + j]
        elif trip.lp.d == driver.address:
            total_d += x[i * valid_trips + j]
    mdl.add_constraint(ct=total_o == 1, ctname='driverFromHome' + '_' + str(i))
    mdl.add_constraint(ct=total_d == 1, ctname='driverToHome' + '_' + str(i))

print("Number of constraints after driver home trips", mdl.number_of_constraints)

# Wheelchair constraint
for i, driver in enumerate(drivers):
    for j, trip in enumerate(filter(f(driver), all_trips)):
        total = (x[i * valid_trips + j] * trip.space - driver.capacity)
        mdl.add_constraint(ct=total <= 0, ctname='capacity' + '_' + str(i) + '_' + str(j))
print("Number of constraints after wheelchair capacity", mdl.number_of_constraints)

# Pickup at most 15 mins before for primary trips
for i, driver in enumerate(drivers):
    for j, trip in enumerate(filter(f(driver), all_trips)):
        if trip in primary_trips:
            total = ((trip.start - FIFTEEN) - x[INT_VARS_OFFSET + i * valid_trips + j])
            mdl.add_constraint(ct=total <= 0, ctname='pickup' + '_' + str(i) + '_' + str(j))
print("Number of constraints after pickup time constraint", mdl.number_of_constraints)

# Dropoff by the required time for primary trips
for i, driver in enumerate(drivers):
    for j, trip in enumerate(filter(f(driver), all_trips)):
        if trip in primary_trips:
            total = ((x[INT_VARS_OFFSET + i * valid_trips + j] + trip.lp.time) - trip.end)
            mdl.add_constraint(ct=total <= 0, ctname='dropoff' + '_' + str(i) + '_' + str(j))

print("Number of constraints after dropoff time constraint", mdl.number_of_constraints)

total = 0.0
for i, driver in enumerate(drivers):
    for j, trip in enumerate(filter(f(driver), all_trips)):
        total += trip.lp.miles * x[i * valid_trips + j]

print('\n'.join(str(c) for c in mdl.iter_constraints()))

mdl.minimize(total)
mdl.solve()
print("Solve status: " + str(mdl.get_solve_status()))

try:
    print("Obj value: " + str(mdl.objective_value))
except Exception as e:
    print(e)
    pass

try:
    for var in x:
        print(var.get_name() + ": " + str(var.solution_value))
except Exception as e:
    print(e)
    pass

with open("modeltrips.txt", "w+") as o:
    o.write("Trip_id, start, end, pickup, dropoff, time, type, miles\n")
    for trip in all_trips:
        o.write(str(trip.id) + ',"' + str(trip.lp.o) + '","' + str(trip.lp.d) + '",' + str(trip.start) + "," + str(
            trip.end) + "," + str(trip.lp.time) + "," + str(trip.type) + "," + str(trip.lp.miles) + "\n")

totalMiles = 0
count = 0
with open("modelsoln.txt", "w+") as o:
    o.write("Driver_id, Trip_id, Time, Miles, Trip_Time, Trip_type, Trip_start, Trip_end\n")
    for i, driver in enumerate(drivers):
        for j, trip in enumerate(filter(f(driver), all_trips)):
            if x[i * valid_trips + j].solution_value == 1:
                count += 1
                totalMiles += trip.lp.miles
                o.write(str(driver.id) + "," + str(trip.id) + "," + str(
                    x[INT_VARS_OFFSET + i * valid_trips + j].solution_value) + "," + str(trip.lp.miles) + "," + str(
                    trip.lp.time) + "," + str(trip.type) + ',"' + str(trip.lp.o) + '","' + str(trip.lp.d) + '"\n')
                print("Driver ", driver.id, " goes from ", trip.lp.o, " to ", trip.lp.d, " at ",
                      x[INT_VARS_OFFSET + i * valid_trips + j].solution_value)
print("Number of trips", count)
print("Total miles traveled", totalMiles)
print("Ended", datetime.now())
