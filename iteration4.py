import pandas as pd
from Driver import Driver
from Trip import Trip, TripType, speed
from docplex.mp.model import Model
from docplex.mp.progress import ProgressListener

from datetime import datetime

NUM_TRIPS = float('inf')
NUM_DRIVERS = float('inf')
FIFTEEN = 0.01041666666

def filtered(d, iter):
    return filter(lambda t: not ((t.lp.o in driverNodes and t.lp.o[3:] != d.address) or (t.lp.d in driverNodes and t.lp.d[3:] != d.address)) and t.los in d.los,iter)

class Listener(ProgressListener):
    """
    Sample Listener found on IBM DoCPLEX Forums
    """
    def __init__(self, time, gap):
        ProgressListener.__init__(self)
        self._time = time
        self._gap = gap

    def notify_progress(self, data):
        print('Elapsed time: %.2f' % data.time)
        if data.has_incumbent:
            print('Current incumbent: %f' % data.current_objective)
            print('Current gap: %.2f%%' % (100. * data.mip_gap))
            # If we are solving for longer than the specified time then
            # stop if we reach the predefined alternate MIP gap.
            if data.time > self._time or data.mip_gap < self._gap:
                print('ABORTING')
                self.abort()
        else:
            print('No incumbent yet')

print("Started", datetime.now())
print("Average Speed assumed: ",speed)
t = datetime.now()
trip_df = pd.read_csv("../Data/in_trips.csv", keep_default_na=False)
driver_df = pd.read_csv("../Data/in_drivers.csv", keep_default_na=False)
mdl = Model(name="Patient Transport")

# Input Data Structures
drivers = list() # List of all Drivers
primary_trips = set()
all_trips = dict() # Maps Trip-ID to Trip Object
driverNodes = set() # All Driver Nodes
driverStart = set() # Starting Nodes of Driver
driverEnd = set() # Ending Nodes of Driver

requestNodes = set() # Nodes of request trips
requestStart = set() # Starting nodes of request trips
requestEnd = set() # Ending nodes of request trips
requestPair = dict() # Map from request start to request end
nodeCaps = dict() # Map from node to capacity delta

# Decision Variable Structures
trips = dict() # Map from driver to map of trip to model variable
times = dict() # Map from driver to map of trip to model variable
caps = dict() # Map from driver to map of trip to model variable

# Additional Structures
intrips = dict() # Map from driver to Map from location to list of trips
outtrips = dict() # Map from driver to Map from location to list of trips


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
    # start = "O:" + row['Address']
    # end = "D:" + row['Address']
    # print(start, end)
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
        # start = "O:" + row['scrub_trip_pickup_address']
        # end = "D:" + row['scrub_trip_dropoff_address']
        # print(start, end)
        pick = float(row['trip_pickup_time'])
        drop = float(row['trip_dropoff_time'])
        cap = 1 if row['trip_los'] == 'A' else 1.5
        if drop == 0.0:
            drop = 1.0
        id = row['trip_id']
        if id.endswith('A'):
            type = TripType.B
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
            t = Trip(start, end, cap, id, type, pick, drop, True, prefixLen=4)
            all_trips[id] = t
            primary_trips.add(t)
            if start not in outtrips:
                outtrips[start] = {t}
            else:
                outtrips[start].add(t)
            if end not in intrips:
                intrips[end] = {t}
            else:
                intrips[end].add(t)
            count += 1
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
            t = Trip(start, end, cap, id, type, pick, drop, True,prefixLen=4)
            all_trips[id] = t
            primary_trips.add(t)
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
    print("Not enough nodes", len(requestNodes), count )
    exit(1)

print("Number of Trips:", count)
id = 1
"""
Trips from Driver Start locations to Start location of any request
"""
for dS in driverStart:
    for rS in requestStart:
        t = Trip(dS, rS, 0, id, TripType.INTER_A, 0.0, 1.0, True)
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
        t = Trip(rE, dE, 0, id, TripType.INTER_B, 0.0, 1.0, True)
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
        if rS == rE:
            continue
        t = Trip(rS, rE, 0, id, TripType.C, 0.0, 1.0, True)
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
        trips[d][t] = mdl.binary_var(name='y' +'_' + str(d.id) +'_' + str(t.id))
        # if d.los == 'A' and t.los != 'A':
        #     mdl.add_constraint(ct=trips[d][t] == 0)
        times[d][t] = mdl.continuous_var(lb=0, ub=1, name='t' +'_' + str(d.id) +'_' + str(t.id))
        caps[d][t] = mdl.continuous_var(lb=0, ub=d.capacity, name='q' +'_' + str(d.id) +'_' + str(t.id))

# print(outtrips)
# print(intrips)
# print(all_trips)

"""
Objective function
"""
obj = 0
for driver_trips in trips.values():
    for t, var in driver_trips.items():
        obj += t.lp.miles * var
mdl.minimize(obj)
print("Defined Objective Function")
"""
Request Requirements
"""
for trp in all_trips:
    if isinstance(trp, str):
        total = 0
        for d in drivers:
            if all_trips[trp].los in d.los:
                total += trips[d][all_trips[trp]]
        mdl.add_constraint(ct=total == 1)
print("Set Primary Trip Requirement Constraint")
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
    mdl.add_constraint(ct= totalin <= 1, ctname='flowin' + '_' + str(rN)[:5])
    mdl.add_constraint(ct= totalout >= -1, ctname='flowout' + '_' + str(rN)[:5])
    mdl.add_constraint(ct= totalin + totalout == 0, ctname='flowinout' + '_' + str(rN)[:5])

for d in drivers:
    for dS in driverStart:
        if dS[3:] != d.address:
            continue
        total = 0
        for otrip in filtered(d, outtrips[dS]):
            total -= trips[d][otrip]
        mdl.add_constraint(ct= total == -1, ctname='driverout' + '_' + str(d.id))
for d in drivers:
    for dE in driverEnd:
        if dE[3:] != d.address:
            continue
        total = 0
        for intrip in filtered(d, intrips[dE]):
            total += trips[d][intrip]
        mdl.add_constraint(ct= total == 1, ctname='driverin' + '_'  + str(d.id))

print("Set flow conservation constraints")

"""
Time Constraints
"""
for d in drivers:
    for loc in requestEnd.union(driverEnd):
        for intrip in filtered(d, intrips[loc]):
            mdl.add_constraint(ct=times[d][intrip] + intrip.lp.time <= intrip.end)
print("Set arrival time constriants")

for trp in all_trips:
    if isinstance(trp, str):
        trip = all_trips[trp]
        for d in drivers:
            if all_trips[trp].los in d.los:
                mdl.add_constraint(ct=times[d][trip] >= trip.start - FIFTEEN)
print("Set departure time constraints")

"""
Precedence Constraints
"""
for trp in all_trips:
    if isinstance(trp, str):
        if trp.endswith('A') and (trp[:-1] + 'B') in all_trips:
            main_trip = all_trips[trp]
            alt_trip = all_trips[trp[:-1] + "B"]
            for d in drivers:
                if all_trips[trp].los in d.los:
                    mdl.add_constraint(ct=times[d][main_trip] + main_trip.lp.time <= times[d][alt_trip])
print("Set primary trip precedence constraints")

for d in drivers:
    for loc in requestNodes:
        incount = 0
        for intrip in filtered(d, intrips[loc]):
            for otrip in filtered(d, outtrips[loc]):
                mdl.add_indicator(trips[d][intrip], times[d][intrip] + intrip.lp.time <= times[d][otrip])
print("Set incoming trip before outgoing trip constraints")

for loc in requestNodes:
    total = 0
    for d in drivers:
        for intrip in filtered(d, intrips[loc]):
            total += d.id * trips[d][intrip]
        for otrip in filtered(d, outtrips[loc]):
            total -= d.id * trips[d][otrip]
    mdl.add_constraint(ct= total == 0)

for rS in requestStart:
    rE = requestPair[rS]
    total = 0
    for d in drivers:
        for intrip in filtered(d, intrips[rE]):
            total += d.id * trips[d][intrip]
        for otrip in filtered(d, outtrips[rS]):
            total -= d.id * trips[d][otrip]
    mdl.add_constraint(ct= total == 0)
print("Set incoming driver is the same as outgoing driver constraints")

"""
Capacity Constraints
"""
for d in drivers:
    for loc in requestNodes:
        for otrip in filtered(d, outtrips[loc]):
            for intrip in filtered(d, intrips[loc]):
                mdl.add_indicator(trips[d][intrip], caps[d][intrip] + nodeCaps[loc] == caps[d][otrip])
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

pL = Listener(3600, 0.01)
mdl.add_progress_listener(pL)

mdl.solve()
print("Solve status: " + str(mdl.get_solve_status()))
try:
    print("Obj value: " + str(mdl.objective_value))
    for d, driver_trips in trips.items():
        for t, var in driver_trips.items():
            if var.solution_value == 1:
                print(str(d.id) + " : "+ str(t) + " at time ", str(times[d][t].solution_value), "holding ",
                      str(caps[d][t].solution_value), " out of total capacity ", d.capacity )
    # for driver_trips in times.values():
    #     for t, var in driver_trips.items():
    #         print(var.get_name() + ": " + str(var.solution_value))
    driverMiles = dict()
    with open('assignments.csv', 'w') as output:
        output.write('driver_id, trip_id, time, cap, miles\n')
        for d, driver_trips in trips.items():
            driverMiles[d] = 0
            for t, var in driver_trips.items():
                if t not in primary_trips:
                    continue
                if var.solution_value == 1:
                    driverMiles[d] += t.lp.miles
                    output.write(str(d.id) + "," + str(t.id) + "," + str(times[d][t].solution_value) + "," +
                          str(caps[d][t].solution_value) +"," + str(t.lp.miles) + "\n")
    def tripGen():
        for d, driver_trips in trips.items():
            for t, var in driver_trips.items():
                if t not in primary_trips or var.solution_value != 1:
                    continue
                yield (d, t)

    with open('final_output.csv', 'w') as output:
        output.write('trip_id, driver_id,driver_name ,trip_pickup_address, trip_pickup_time, est_pickup_time, trip_dropoff_adress, trip_dropoff_time, est_dropoff_time, trip_los, est_miles, est_time\n')
        for d, t in sorted(tripGen(), key=lambda x: times[x[0]][x[1]].solution_value):
                output.write(str(t.id) + "," + str(d.id) + "," + str(d.name) + ",\"" + str(t.lp.o[4:]) + "\"," + str(t.start) + "," + str(times[d][t].solution_value) + ",\"" +
                             str(t.lp.d[4:]) + "\"," + str(t.end) + "," + str(times[d][t].solution_value + t.lp.time) + "," +
                      str(t.los) +"," + str(t.lp.miles) +"," + str(t.lp.time) + "\n")
    print("Total Number of primary trip miles by each driver: ")
    print(driverMiles)
except Exception as e:
    print(e)

print("Ended", datetime.now())


