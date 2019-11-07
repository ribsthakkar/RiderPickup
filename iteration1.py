import pandas as pd
from Driver import Driver
from Trip import Trip, TripType
import pyOpt
from pyOpt import pyALHSO
import numpy as np
from scipy.optimize import minimize
import cplex
from docplex.cp.model import CpoModel
from docplex.mp.model import Model


# geo_api = "78bdef6c2b254abaa78c55640925d3db"
# # get lat,lon for l1 and l2
# geolocator = OpenCageGeocode(geo_api)
# l1loc = geolocator.geocode("2101 Rio Grande st Austin,TX")
# print(l1loc[0]['geometry']['lat'])
# exit(1)
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
        cap = 1 if row['trip_los'] == 'A' else 1.5
        locations.add(o)
        locations.add(d)
        t = Trip(o, d, cap, id, type, start, end)
        primary_trips.add(t)
        location_pair.add((o,d))
        if o not in outlfow_trips:
            outlfow_trips[o] = {t}
        else:
            outlfow_trips[o].add(t)
        if d not in inflow_trips:
            inflow_trips[d] = {t}
        else:
            inflow_trips[d].add(t)
        count += 1
        if count == 2:
            break
id = 1

for index, row in driver_df.iterrows():
    cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
    drivers.add(Driver(row['Driver'], row['Address'], cap))
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
        if o is not d and (o,d) not in location_pair:
            t = Trip(o, d, 0, id, TripType.INTER, 0.0, 1.0)
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
print("Number of primary trips ", len(primary_trips))
print("Number of possible secondary trips", len(secondary_trips))
print("Total Number of possible trips", len(all_trips))
indices = {k: v for v, k in enumerate(all_trips)}
INT_VARS_OFFSET = len(all_trips) * len(drivers)



# Formulate optimization problem
"""
For each driver
For each location
"""
mdl = Model(name="Patient Transport")
x = []

for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        x.append(mdl.binary_var(name='y' +'_' + str(i) +'_' + str(j)))

for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        x.append(mdl.continuous_var(lb=0, ub=1, name='t' +'_' + str(i) +'_' + str(j)))
#Inflow = outflow for all locations
for loc in locations:
    for i, d in enumerate(drivers):
        total = 0.0
        for intrip in inflow_trips[loc]:
            total += x[i * len(all_trips) + indices[intrip]]
        for otrip in outlfow_trips[loc]:
            total -= x[i * len(all_trips) + indices[otrip]]
        mdl.add_constraint(ct= total == 0 , ctname='flowinout' + '_' + str(hash(loc))[:5] + '_' + str(i))
# Inflow before outflow for all locations except driver home
for loc in locations:
    for i, d in enumerate(drivers):
        total = 0.0
        for intrip in inflow_trips[loc]:
            for otrip in outlfow_trips[loc]:
                total = (x[INT_VARS_OFFSET + i * len(all_trips) + indices[intrip]] + intrip.lp.time) - x[INT_VARS_OFFSET + i * len(all_trips) + indices[otrip]]
                if loc in driverLocations: # leave home before coming back
                    mdl.add_constraint(ct=total >= 0, ctname='outb4in' + '_' + str(hash(loc))[:5] + '_' + str(i))
                else:
                    mdl.add_constraint(ct= total <= 0 , ctname='inb4out' + '_' + str(hash(loc))[:5] + '_' + str(i))

# Only one driver per trip
for j, trip in enumerate(all_trips):
    total = 0
    for i, driver in enumerate(drivers):
        total += x[i * len(all_trips) + j]
    if j < len(primary_trips):
        mdl.add_constraint(ct= total == 1 , ctname='primaryTrip' +'_' + str(j))
    else:
        mdl.add_constraint(ct= total <=1 , ctname='secondaryTrip' +'_' + str(j))
#
#Trips can't overlap for a driver
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        for k, trip2 in enumerate(all_trips):
            if trip is not trip2:
                total = ((x[INT_VARS_OFFSET + i * len(all_trips) + k] - x[INT_VARS_OFFSET + i * len(all_trips) + j])
                         + ((x[INT_VARS_OFFSET + i * len(all_trips) + j] + trip.lp.time) -
                            x[INT_VARS_OFFSET + i * len(all_trips) + k]) - trip.lp.time)
                mdl.add_constraint(ct= total <= 0, ctname='tripConflict'+'_'  + str(i) +'_' + str(j)+'_'  + str(k))
# Wheelchair constraint
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        total = (x[i * len(all_trips) + j]*trip.space - driver.capacity)
        mdl.add_constraint(ct=total <= 0, ctname='capacity'+'_' +str(i)+'_' +str(j))

# Pickup at most 15 mins before
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        total = ((trip.start - 0.01041666666) - x[INT_VARS_OFFSET + i * len(all_trips) + j])
        mdl.add_constraint(ct= total <= 0,ctname='pickup' +'_' + str(i)+'_'  + str(j))
# Dropoff by the required time
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        total = ((x[INT_VARS_OFFSET + i * len(all_trips) + j] + trip.lp.time) - trip.end)
        mdl.add_constraint(ct= total <= 0,ctname='dropoff'+'_' +str(i)+'_'  + str(j))

total = 0.0
for i, driver in enumerate(drivers):
    for j, trip in enumerate(all_trips):
        total += trip.lp.time * x[i * len(all_trips) + j]

mdl.minimize(total)
mdl.solve()
print("Solve status: " + str(mdl.get_solve_status()))
print("Obj value: " + str(mdl.objective_value))
for var in x:
    print(var.get_name() + ": "+ str(var.solution_value))

# constraints = []
# # Inflow = outflow for all locations except driver home
# for loc in locations:
#     for i, d in enumerate(drivers):
#         def cons(x):
#             total = 0.0
#             for intrip in inflow_trips[loc]:
#                 total += x[i * len(all_trips) + indices[intrip]]
#             for otrip in outlfow_trips[loc]:
#                 total += x[i * len(all_trips) + indices[otrip]]
#             return total
#         constraints.append({'type':'eq', 'fun':cons})
#
# # Each trip only has one driver if primary and at most one driver if not primary
# for j, trip in enumerate(all_trips):
#     def cons(x):
#         total = 0
#         for i, driver in enumerate(drivers):
#             total += x[i * len(all_trips) + j]
#         return -(total - 1)
#     if j < len(primary_trips):
#         constraints.append({'type':'eq', 'fun':cons})
#     else:
#         constraints.append({'type':'ineq', 'fun':cons})
#
# # Trips do not overlap for each driver
# for i, driver in enumerate(drivers):
#     for j, trip in enumerate(all_trips):
#         for k, trip2 in enumerate(all_trips):
#             if trip is not trip2:
#                 def cons(x):
#                     total = ((x[i * len(all_trips) + k]*x[INT_VARS_OFFSET+i * len(all_trips) + k]-x[i * len(all_trips) + j]*x[INT_VARS_OFFSET+i * len(all_trips) + j])
#                                    + (x[i * len(all_trips) + j] *(x[INT_VARS_OFFSET+i * len(all_trips) + j]+trip.lp.time) - x[i * len(all_trips) + k]*x[INT_VARS_OFFSET+i * len(all_trips) + k]) - trip.lp.time)
#                     return -total
#                 constraints.append({'type': 'ineq', 'fun': cons})
#
# # Wheelchair constraint
# for i, driver in enumerate(drivers):
#     for j, trip in enumerate(all_trips):
#         def cons(x):
#             return -(x[i * len(all_trips) + j]*trip.space - driver.capacity)
#         constraints.append({'type':'ineq', 'fun':cons})
#
#
# # Pickup at most 15 mins before
# for i, driver in enumerate(drivers):
#     for j, trip in enumerate(all_trips):
#         def cons(x):
#             return -(x[i * len(all_trips) + j] * (trip.start  - 0.01041666666) - x[i * len(all_trips) + j]* x[INT_VARS_OFFSET + i * len(all_trips) + j])
#         constraints.append({'type':'ineq', 'fun':cons})
#
# # Dropoff by the required time
# for i, driver in enumerate(drivers):
#     for j, trip in enumerate(all_trips):
#         def cons(x):
#             return -(x[i * len(all_trips) + j] * (x[INT_VARS_OFFSET + i * len(all_trips) + j] + trip.lp.time) - x[i * len(all_trips) + j] * trip.end)
#         constraints.append({'type':'ineq', 'fun':cons})
#
# # Solve Optimization Problem
# for i, driver in enumerate(drivers):
#     for j, trip in enumerate(all_trips):
#         print("Driver i ", driver.name, " does trip ", j, " from ", trip.lp.o, " to ", trip.lp.d, " in ", trip.lp.time, " minutes")
# opt_prob = pyOpt.Optimization('Hospital Dropoff Problem',objfunc)
# opt_prob.addObj('Time Traveled')
#
#
#
# bounds = []