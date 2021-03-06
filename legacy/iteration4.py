from datetime import datetime

import pandas as pd
from Driver import Driver
from Trip import Trip, TripType, InvalidTripException
from constants import *
from docloud.status import JobSolveStatus
from docplex.mp.model import Model
from docplex.mp.utils import DOcplexException
from listeners import TimeListener, GapListener

NUM_TRIPS = 55  # float('inf')
NUM_DRIVERS = float('inf')
invalid_trips = {(-1, -1.5), (-1.5, -1), (1, 1.5), (1, -1.5)}


def filtered(d, iter):
    return filter(lambda t: not ((t.lp.o in driverNodes and t.lp.o[3:] != d.address) or (
                t.lp.d in driverNodes and t.lp.d[3:] != d.address)) and t.los in d.los
                            and not (abs(nodeCaps[t.lp.o] + nodeCaps[t.lp.d]) > d.capacity), iter)


# ((abs(nodeCaps[t.lp.o]) <= d.capacity + nodeCaps[t.lp.d]) and (d.capacity >= nodeCaps[t.lp.o] + nodeCaps[t.lp.d]))


print("Started", datetime.now())
t = datetime.now()
trip_df = pd.read_csv("../Data/in_trips.csv", keep_default_na=False)
driver_df = pd.read_csv("../Data/in_drivers.csv", keep_default_na=False)
# trip_df = pd.read_csv("Trips.csv", keep_default_na=False)
# driver_df = pd.read_csv("Drivers.csv", keep_default_na=False)
mdl = Model(name="Patient Transport")

# Input Data Structures
drivers = list()  # List of all Drivers
primary_trips = set()
all_trips = dict()  # Maps Trip-ID to Trip Object
driverNodes = set()  # All Driver Nodes
driverStart = set()  # Starting Nodes of Driver
driverEnd = set()  # Ending Nodes of Driver

requestNodes = set()  # Nodes of request trips
requestStart = set()  # Starting nodes of request trips
requestEnd = set()  # Ending nodes of request trips
requestPair = dict()  # Map from request start to request end
nodeCaps = dict()  # Map from node to capacity delta
nodeDeps = dict()  # Earliest departure time from a node
nodeArrs = dict()  # earliest arrival time to a node
primaryTID = dict()  # Map from starting location to ID of primary trip from that location

# Decision Variable Structures
trips = dict()  # Map from driver to map of trip to model variable
times = dict()  # Map from driver to map of trip to model variable
caps = dict()  # Map from driver to map of trip to model variable

# Additional Structures
intrips = dict()  # Map from driver to Map from location to list of trips
outtrips = dict()  # Map from driver to Map from location to list of trips

# Preprocess input data

"""
Driver Locations
"""
count = 0
for index, row in driver_df.iterrows():
    if row['Available?'] != 1:
        continue
    cap = 2
    drivers.append(Driver(row['ID'], row['Name'], row['Address'], cap, row['Vehicle_Type']))
    start = str(hash(row['ID']))[:0] + "Or:" + row['Address']
    end = str(hash(row['ID']))[:0] + "De:" + row['Address']
    driverNodes.add(start)
    driverNodes.add(end)
    driverStart.add(start)
    driverEnd.add(end)
    nodeCaps[start] = 0
    nodeCaps[end] = 0

    count += 1
    if count == NUM_DRIVERS:
        break
print("Number of Drivers:", count)
count = 0
for index, row in trip_df.iterrows():
    if not row['trip_status'] == "CANCELED":
        start = str(hash(row['trip_id']))[1:4] + ":" + row['trip_pickup_address']
        end = str(hash(row['trip_id']))[1:4] + ":" + row['trip_dropoff_address']
        pick = float(row['trip_pickup_time'])
        drop = float(row['trip_dropoff_time'])
        cap = 1 if row['trip_los'] == 'A' else 1.5
        if drop == 0.0:
            drop = 1.0
        id = row['trip_id']
        type = None
        if id.endswith('A'):
            type = TripType.B
        elif id.endswith('B'):
            type = TripType.D
        requestStart.add(start)
        requestEnd.add(end)
        requestPair[start] = end
        a = len(requestNodes)
        requestNodes.add(start)
        if a == len(requestNodes):
            print(start, end)
            exit(1)
        b = len(requestNodes)
        requestNodes.add(end)
        if b == len(requestNodes):
            print(start, end)
            exit(1)
        nodeCaps[start] = cap
        nodeCaps[end] = -cap
        t = Trip(start, end, cap, id, type, pick, drop, prefix=True, prefixLen=4)
        nodeArrs[start] = drop - t.lp.time  # 0
        nodeDeps[start] = pick  # max(0, pick - BUFFER)
        nodeArrs[end] = drop
        nodeDeps[end] = pick + t.lp.time  # 0 # max(0, pick - BUFFER) + t.lp.time
        # nodeArrs[start] = 1
        # nodeDeps[start] = 0
        # nodeArrs[end] = 1
        # nodeDeps[end] = 0
        all_trips[id] = t
        primary_trips.add(t)
        primaryTID[start] = t.id
        if start not in outtrips:
            outtrips[start] = {t}
        else:
            outtrips[start].add(t)
        if end not in intrips:
            intrips[end] = {t}
        else:
            intrips[end].add(t)
        count += 1
        if count == NUM_TRIPS:
            break

if len(requestNodes) != 2 * count:
    print("Not enough nodes", len(requestNodes), count)
    exit(1)

print("Number of Trips:", count)
id = 1
"""
Trips from Driver Start locations to Start location of any request
"""
for dS in driverStart:
    for rS in requestStart:
        t = Trip(dS, rS, 0, id, TripType.INTER_A, 0.0, 1.0, prefix=True)
        if dS not in outtrips:
            outtrips[dS] = {t}
        else:
            outtrips[dS].add(t)
        if rS not in intrips:
            intrips[rS] = {t}
        else:
            intrips[rS].add(t)
        id += 1
        all_trips[id] = t

"""
Trips for End location of any request to Driver End locations
"""
for dE in driverEnd:
    for rE in requestEnd:
        t = Trip(rE, dE, 0, id, TripType.INTER_B, 0.0, 1.0, prefix=True)
        if rE not in outtrips:
            outtrips[rE] = {t}
        else:
            outtrips[rE].add(t)
        if dE not in intrips:
            intrips[dE] = {t}
        else:
            intrips[dE].add(t)
        id += 1
        all_trips[id] = t

"""
Trips from any request location to any other request location
"""
for rS in requestNodes:
    for rE in requestNodes:
        if rS == rE or (rS in requestPair and requestPair[rS] == rE) or (rE in requestPair and requestPair[rE] == rS):
            continue
        try:
            t = Trip(rS, rE, 0, id, TripType.C, nodeDeps[rS], nodeArrs[rE], prefix=True)
        except InvalidTripException:
            # print(rS, rE, nodeDeps[rS], nodeArrs[rE])
            continue
        if rS not in outtrips:
            outtrips[rS] = {t}
        else:
            outtrips[rS].add(t)
        if rE not in intrips:
            intrips[rE] = {t}
        else:
            intrips[rE].add(t)
        id += 1
        all_trips[id] = t

# """
# Trips from driver home start to driver home end if not needed
# """
# for dS in driverStart:
#     for dE in driverEnd:
#         t = Trip(dS, dE, 0, id, TripType.INTER_B, 0.0, 1.0)
#         if dS not in outtrips:
#             outtrips[dS] = {t}
#         else:
#             outtrips[dS].add(t)
#         if dE not in intrips:
#             intrips[dE] = {t}
#         else:
#             intrips[dE].add(t)
#         id += 1
#         all_trips[id] = t
# print(sp)
"""
Create Decision Variables for Each Driver
"""
for d in drivers:
    trips[d] = dict()
    times[d] = dict()
    caps[d] = dict()
    for t in filtered(d, all_trips.values()):
        # if (t.lp.o in driverNodes and t.lp.o[2:] != d.address) or (t.lp.d in driverNodes and t.lp.d[2:] != d.address):
        #     continue
        trips[d][t] = mdl.binary_var(name='y' + '_' + str(d.id) + '_' + str(t.id))
        # if d.los == 'A' and t.los != 'A':
        #     mdl.add_constraint(ct=trips[d][t] == 0)
        times[d][t] = mdl.continuous_var(lb=0, ub=1, name='t' + '_' + str(d.id) + '_' + str(t.id))
        mdl.add_constraint(times[d][t] - trips[d][t] <= 0)
        # mdl.add_equivalence(trips[d][t], times[d][t] > 0)
        caps[d][t] = mdl.continuous_var(lb=0, ub=d.capacity, name='q' + '_' + str(d.id) + '_' + str(t.id))
        mdl.add_constraint(caps[d][t] - trips[d][t] * d.capacity <= 0)

# print(outtrips)
# print(intrips)
# print(all_trips)

"""
Objective function
"""
obj = 0
for d, driver_trips in trips.items():
    for t, var in driver_trips.items():
        obj += t.lp.miles * var
print("Defined Objective Function")
"""
Request Requirements
"""
# for trp in all_trips:
#     if isinstance(trp, str):
#         total = 0
#         for d in drivers:
#             if all_trips[trp].los in d.los and 1 > d.capacity - all_trips[trp].space >= 0:
#                 total += trips[d][all_trips[trp]]
#         if total is not 0:
#             con = mdl.add_constraint(ct=total == 1)
constraintsToRem = set()
for trp in all_trips:
    if isinstance(trp, str):
        total = 0
        for d in drivers:
            if all_trips[trp].los in d.los:
                total += trips[d][all_trips[trp]]
        con = mdl.add_constraint(ct=total == 1)
        constraintsToRem.add(con)
#         con.set_priority(Priority.VERY_LOW)
# for rS in requestStart:
#     flowout = 0
#     for d in drivers:
#         for otirp in filtered(d, outtrips[rS]):
#             flowout += trips[d][otirp]
#     mdl.add_constraint(flowout == 1)
#
# for rE in requestEnd:
#     flowin = 0
#     for d in drivers:
#         for intrip in filtered(d, intrips[rE]):
#             flowin += trips[d][intrip]
#     mdl.add_constraint(flowin == 1)
# print("Set Primary Trip Requirement Constraint")
"""
Flow Conservation
"""
for rN in requestNodes:
    totalin = 0
    totalout = 0
    for d in drivers:
        for intrip in filtered(d, intrips[rN]):
            totalin += trips[d][intrip]
        for otrip in filtered(d, outtrips[rN]):
            totalout -= trips[d][otrip]
    mdl.add_constraint(ct=totalin <= 1, ctname='flowin' + '_' + str(rN)[:5])
    mdl.add_constraint(ct=totalout >= -1, ctname='flowout' + '_' + str(rN)[:5])
    mdl.add_constraint(ct=totalin + totalout == 0, ctname='flowinout' + '_' + str(rN)[:5])
for d in drivers:
    for dS in driverStart:
        if dS[3:] != d.address:
            continue
        total = 0
        for otrip in filtered(d, outtrips[dS]):
            total -= trips[d][otrip]
        mdl.add_constraint(ct=total == -1, ctname='driverout' + '_' + str(d.id))
for d in drivers:
    for dE in driverEnd:
        if dE[3:] != d.address:
            continue
        total = 0
        for intrip in filtered(d, intrips[dE]):
            total += trips[d][intrip]
        mdl.add_constraint(ct=total == 1, ctname='driverin' + '_' + str(d.id))

print("Set flow conservation constraints")

"""
Time Constraints
"""
# for d in drivers:
#     for loc in requestNodes.union(driverEnd):
#         for intrip in filtered(d, intrips[loc]):
#             mdl.add_indicator(trips[d][intrip], times[d][intrip] + intrip.lp.time <= intrip.end)
dropOffPenalty = 800
# for loc in requestEnd.union(driverEnd):
for loc in requestNodes:
    intripSum = 0
    intripTimes = 0
    intripEnds = nodeArrs[loc]
    for d in drivers:
        for intrip in filtered(d, intrips[loc]):
            intripSum += times[d][intrip]
            intripTimes += intrip.lp.time * trips[d][intrip]
            # intripEnds += intrip.end * trips[d][intrip]
    mdl.add_constraint(intripSum + intripTimes <= intripEnds)
    # obj += dropOffPenalty * ((intripSum + intripTimes) - intripEnds)
print("Set arrival time constriants")

# for d in drivers:
#     for loc in requestStart:
#         # print(loc)
#         for otrip in filtered(d, outtrips[loc]):
#             mdl.add_indicator(trips[d][otrip], times[d][otrip] >= otrip.start - BUFFER)
#             # mdl.add_indicator(trips[d][otrip], times[d][otrip] <= otrip.start + BUFFER)
pickupEarlyPenalty = 600
pickupLatePenalty = 200
# for loc in requestStart:
for loc in requestNodes:
    otripSum = 0
    otripStarts = nodeDeps[loc]
    for d in drivers:
        for otrip in filtered(d, outtrips[loc]):
            otripSum += times[d][otrip]
            # otripStarts += otrip.start * trips[d][otrip]
        # obj += pickupEarlyPenalty * (otripStarts - (otripSum + BUFFER))
        # obj += pickupLatePenalty * (otripStarts - (otripSum - BUFFER))
    mdl.add_constraint(otripSum + BUFFER >= otripStarts)
    mdl.add_constraint(otripSum <= otripStarts + BUFFER)
print("Set departure time constraints")

"""
Precedence Constraints
"""
for trp in all_trips:
    if isinstance(trp, str):
        if trp.endswith('A') and (trp[:-1] + 'B') in all_trips:
            main_trip = all_trips[trp]
            main_trip_loc = all_trips[trp].lp.d
            alt_trip_loc = all_trips[trp[:-1] + "B"].lp.o
            isum = 0
            itimeSum = 0
            for d in drivers:
                for intrip in filtered(d, intrips[main_trip_loc]):
                    isum += times[d][intrip]
                    itimeSum += intrip.lp.time * trips[d][intrip]
            osum = 0
            for d2 in drivers:
                for otrip in filtered(d2, outtrips[alt_trip_loc]):
                    osum += times[d2][otrip]
                    # print(d.id, d2.id, repr(intrip), repr(otrip))
                    # mdl.add_indicator(trips[d][intrip], times[d][intrip] + intrip.lp.time <= times[d2][otrip])
            mdl.add_constraint(isum + itimeSum <= osum)
print("Set primary trip precedence constraints")

for loc in requestNodes:
    insum, osum = 0, 0
    timeSum = 0
    for d in drivers:
        for intrip in filtered(d, intrips[loc]):
            insum += times[d][intrip]
            timeSum += trips[d][intrip] * intrip.lp.time
        for otrip in filtered(d, outtrips[loc]):
            osum += times[d][otrip]
    mdl.add_constraint(insum + timeSum <= osum)
print("Set incoming trip before outgoing trip constraints")

for loc in requestNodes:
    total = 0
    for d in drivers:
        for intrip in filtered(d, intrips[loc]):
            total += d.id * trips[d][intrip]
        for otrip in filtered(d, outtrips[loc]):
            total -= d.id * trips[d][otrip]
    mdl.add_constraint(ct=total == 0)

for rS in requestStart:
    rE = requestPair[rS]
    total = 0
    for d in drivers:
        for intrip in filtered(d, intrips[rE]):
            total += d.id * trips[d][intrip]
        for otrip in filtered(d, outtrips[rS]):
            total -= d.id * trips[d][otrip]
    mdl.add_constraint(ct=total == 0)
print("Set incoming driver is the same as outgoing driver constraints")

"""
Capacity Constraints
"""
# for d in drivers:
#     for loc in requestNodes:
#         for otrip in filtered(d, outtrips[loc]):
#             for intrip in filtered(d, intrips[loc]):
#                 mdl.add_if_then(trips[d][intrip] + trips[d][otrip] == 2, then_ct= nodeCaps[loc] == caps[d][otrip] - caps[d][intrip]) # !!!! MAJOR FIX
for loc in requestNodes:
    incaps = 0
    ocaps = 0
    tripsum = 0
    for d in drivers:
        for otrip in filtered(d, outtrips[loc]):
            ocaps += caps[d][otrip]
        for intrip in filtered(d, intrips[loc]):
            incaps += caps[d][intrip]
    mdl.add_constraint(ocaps == incaps + nodeCaps[loc])
print("Set capacity value constraints")

for d in drivers:
    for loc in driverStart:
        for otrip in filtered(d, outtrips[loc]):
            mdl.add_constraint(ct=caps[d][otrip] == 0)
    for loc in driverEnd:
        for intrip in filtered(d, intrips[loc]):
            mdl.add_constraint(ct=caps[d][intrip] == 0)
print("Set initial and final trip capacity constraints")

print("Num variables:", mdl.number_of_variables)
print("Num constraints:", mdl.number_of_constraints)
mdl.minimize(obj)

try:
    pL = TimeListener(3600)
    mdl.add_progress_listener(pL)
    first_solve = mdl.solve()
    print("First solve status: " + str(mdl.get_solve_status()))
    print("First solve obj value: " + str(mdl.objective_value))
    print("Relaxing single rider requirements constraints")
    mdl.remove_constraints(constraintsToRem)
    print("Warm starting from single rider constraint solution")
    mdl.add_mip_start(first_solve)
    mdl.remove_progress_listener(pL)
    pL = GapListener(3600 * 6, 0.01)
    mdl.add_progress_listener(pL)
    mdl.solve()
    print("Final solve status: " + str(mdl.get_solve_status()))
    print("Final Obj value: " + str(mdl.objective_value))

except DOcplexException as e:
    print(e)

finally:
    if mdl.get_solve_status() == JobSolveStatus.FEASIBLE_SOLUTION or mdl.get_solve_status() == JobSolveStatus.OPTIMAL_SOLUTION:
        totalMiles = 0
        for d, driver_trips in trips.items():
            for t, var in driver_trips.items():
                if var.solution_value == 1:
                    totalMiles += t.lp.miles
                    print(str(d.id) + " : " + str(t) + " at time ", str(times[d][t].solution_value), "holding ",
                          str(caps[d][t].solution_value), " out of total capacity ", d.capacity)
                elif var.solution_value == 0 and (
                        abs(times[d][t].solution_value) >= 0.1 or abs(caps[d][t].solution_value) >= 0.1):
                    print("Something Wrong, non ok trips with time/or cap not equal to 0", times[d][t].solution_value,
                          caps[d][t].solution_value)
        # for driver_trips in times.values():
        #     for t, var in driver_trips.items():
        #         print(var.get_name() + ": " + str(var.solution_value))
        print("Total Miles Traveled by all drivers including intermediary trips: ", totalMiles)
        driverMiles = dict()
        with open('assignments.csv', 'w') as output:
            output.write('driver_id, trip_id, time, cap, miles\n')
            for d, driver_trips in trips.items():
                driverMiles[d] = 0
                for t, var in driver_trips.items():
                    if caps[d][t].solution_value >= 0.1:
                        driverMiles[d] += t.lp.miles
                    if t.lp.o not in requestStart:
                        continue
                    if var.solution_value == 1:
                        output.write(
                            str(d.id) + "," + str(primaryTID[t.lp.o]) + "," + str(times[d][t].solution_value) + "," +
                            str(caps[d][t].solution_value) + "," + str(t.lp.miles) + "\n")


        def tripGen():
            for d, driver_trips in trips.items():
                for t, var in driver_trips.items():
                    if t.lp.o not in requestStart or var.solution_value != 1:
                        continue
                    yield (d, t)


        with open('output/final_output' + str(datetime.now()) + '.csv', 'w') as output:
            output.write(
                'trip_id, driver_id,driver_name ,trip_pickup_address, trip_pickup_time, est_pickup_time, trip_dropoff_adress, trip_dropoff_time, est_dropoff_time, trip_los, est_miles, est_time\n')
            for d, t in sorted(tripGen(), key=lambda x: times[x[0]][x[1]].solution_value):
                end_time = -1
                rE = requestPair[t.lp.o]
                for intrip in filtered(d, intrips[rE]):
                    if trips[d][intrip].solution_value == 1:
                        end_time = times[d][intrip].solution_value + intrip.lp.time
                        break
                if end_time < 0:
                    print("Something wrong")
                required_end = all_trips[primaryTID[t.lp.o]].end
                ptrip = all_trips[primaryTID[t.lp.o]]
                output.write(str(primaryTID[t.lp.o]) + "," + str(d.id) + "," + str(d.name) + ",\"" + str(
                    t.lp.o[4:]) + "\"," + str(t.start) + "," + str(times[d][t].solution_value) + ",\"" +
                             str(t.lp.d[4:]) + "\"," + str(rE) + "," + str(required_end) + "," + str(end_time) + "," +
                             str(t.los) + "," + str(ptrip.lp.miles) + "," + str(ptrip.lp.time) + "\n")
        print("Total Number of primary trip miles by each driver: ")
        print(driverMiles)
print("Ended", datetime.now())
