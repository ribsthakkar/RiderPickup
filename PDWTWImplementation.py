import pandas as pd
from Driver import Driver
from Trip import Trip, TripType
from docplex.mp.model import Model
from datetime import datetime

print("Started", datetime.now())
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
ar = dict()
idxes = dict()
tripdex = dict()
TRIPS_TO_DO = 2
NUM_DRIVERS = 1
FIFTEEN = 0.01041666666

last_trip = None
P = [] # Pickup locations
D = [] # Dropoff locations
DP = [] # Initial Depot locations
DD = [] # Final Depot locations

"""
The following varialbes have the prefixes signifying which location they relate to:
P-Pickup
D-Dropoff
DP-Intial Depot
DD-Final Depot

Intial and Final Depot should be the same since driver returns home at teh end of the trip
"""
"""
Decision Variables
"""
x = [] # binary whether trip ij is taken; length of A
PQ = [] # Capacity after node j is visited; Length of N
DQ = [] # Capacity after node j is visited; Length of N
DPQ = [] # Capacity after node j is visited; Length of N
DDQ = [] # Capacity after node j is visited; Length of N

PB = [] # time that node j is visited; Length of N
DB = [] # time that node j is visited; Length of N
DPB = [] # time that node j is visited; Length of N
DDB = [] # time that node j is visited; Length of N


Pv = [] # index of first node that is visited in the route; Length of N
Dv = [] # index of first node that is visited in the route; Length of N
DPv = [] # index of first node that is visited in the route; Length of N
DDv = [] # index of first node that is visited in the route; Length of N


"""
Parameters
"""
Pe = [] # start window of node j; length of N
De = [] # start window of node j; length of N
DPe = [] # start window of node j; length of N
DDe = [] # start window of node j; length of N

Pl = [] # end window of node j; length of N
Dl = [] # end window of node j; length of N
DPl = [] # end window of node j; length of N
DDl = [] # end window of node j; length of N

Pq = [] # demand for each location j; length of N
Dq = [] # demand for each location j; length of N
DPq = [] # demand for each location j; length of N
DDq = [] # demand for each location j; length of N

CAP = 1.5
BIGM = 100000
# Formulate optimization problem
"""
Per section 3.2 of:
Pickup and delivery problem with time windows: a new compact two-index formulation
Maria Gabriela S. Furtadoa, Pedro Munaria, Reinaldo Morabitoa
"""
mdl = Model(name="Patient Transport")

count = 0
for index, row in trip_df.iterrows():
    if not row['trip_status'] == "CANCELED":
        o = row['scrub_trip_pickup_address'] + "P"
        d = row['scrub_trip_dropoff_address'] + "D"
        start = float(row['trip_pickup_time'])
        end = float(row['trip_dropoff_time'])
        if end == 0.0:
            end = 1.0
        cap = 1 if row['trip_los'] == 'A' else 1.5

        idxes[o] = count
        idxes[d] = TRIPS_TO_DO * 2 + count
        P.append(o) # Add to Pickups
        D.append(d) # Add to Dropoffs
        Pe.append(start - FIFTEEN/2) # Add to Pickups open window
        De.append(start - FIFTEEN/2) # Add to Dropoffs open window
        Pl.append(end + FIFTEEN/2) # Add to Pickups close window
        Dl.append(end + FIFTEEN/2) # Add to Dropoffs close window
        Pq.append(CAP) # Add to Pickup capacity
        Dq.append(-CAP) # Add to dropoff capacity

        PQ.append(mdl.continuous_var(lb=0, name='Q_'+str(count))) #Varaible for capacity at location pickup
        DQ.append(mdl.continuous_var(lb=0, name='Q_'+str(TRIPS_TO_DO * 2 + count))) #Varaible for capacity at location dropoff

        PB.append(mdl.continuous_var(lb=0, ub=1, name='B_' + str(count * 2))) #Varaible for time at location pickup
        DB.append(mdl.continuous_var(lb=0, ub=1, name='B_' + str(TRIPS_TO_DO * 2 + count))) #Varaible for time at location dropoff

        Pv.append(mdl.continuous_var(lb=0, name='v_' + str(count * 2))) #Varaible for index of first location on route pickup
        Dv.append(mdl.continuous_var(lb=0, name='v_' + str(TRIPS_TO_DO * 2 + count))) #Varaible for undex of first location on route dropoff

        id = row['trip_id']
        if 'A' in id:
            type = TripType.B
            homes.add(o)
            not_homes.add(d)
        else:
            type = TripType.D
        locations.add(o)
        locations.add(d)
        t = Trip(o, d, cap, id, type, start, end)
        primary_trips.add(t)
        location_pair.add((o,d))
        ar[(o,d)] = t
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
temp = len(P)
temp2 = max(idxes.values())
for index, row in driver_df.iterrows():
    cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
    drivers.add(Driver(row['ID'], row['Driver'], row['Address'], cap))
    locations.add(row['Address'])
    driverLocations.add(row['Address'])
    count += 1
    DP.append(row['Address'])
    DD.append(row['Address'])
    DPe.append(0)  # Add to Pickups open window
    DDe.append(0)  # Add to Dropoffs open window
    DPl.append(1)  # Add to Pickups close window
    DDl.append(1)  # Add to Dropoffs close window
    DPq.append(CAP)  # Add to Pickup capacity
    DDq.append(-CAP)  # Add to dropoff capacity

    DPQ.append(mdl.continuous_var(lb=0, name='Q_' + str(temp + count)))  # Varaible for capacity at location pickup
    DDQ.append(mdl.continuous_var(lb=0, name='Q_' + str(temp2 + count)))  # Varaible for capacity at location dropoff

    DPB.append(mdl.continuous_var(lb=0, ub=1, name='B_' + str(temp + count)))  # Varaible for time at location pickup
    DDB.append(mdl.continuous_var(lb=0, ub=1, name='B_' + str(temp2 + count)))  # Varaible for time at location dropoff

    DPv.append(mdl.continuous_var(lb=0, name='v_' + str(temp + count)))  # Varaible for index of first location on route pickup
    DDv.append(mdl.continuous_var(lb=0, name='v_' + str(temp2 + count))) # Varaible for undex of first location on route dropoff

    idxes["DP" + row['Address']] = temp + count
    idxes["DD" + row['Address']] = temp2 + count


    if count == NUM_DRIVERS:
        break
# Append all of the arrays together to make data structure
Q = PQ + DPQ + DQ + DDQ
B = PB + DPB + DB + DDB
v = Pv + DPv + Dv + DDv
N = P + DP + D + DD
e = Pe + DPe + De + DDe
l = Pl + DPl + Dl + DDl
q = Pq + DPq + Dq + DDq
n = len(P + DP)
print(N)
print(e)
print(l)
print(q)

t = [] # time of traversing trip ij; length of A
c = [] # cost of traversing trip ij; length of A
for i, o in locations:
    for j, d in locations:
        print(o, d)
        for i in inflow_trips:
            print(len(inflow_trips[i]))
        for i in outlfow_trips:
            print(len(outlfow_trips[i]))
        if o != d:
            if (o, d) in location_pair:
                trp = ar[(o, d)]
                x.append(mdl.binary_var(name='x' +'_' + str(i) +'_' + str(j)))
                tripdex[(o,d)] = len(x) - 1
                t.append(trp.lp.time)
                c.append(trp.lp.miles)
            else:
                trp = None
                if o in driverLocations and d in driverLocations:
                    continue
                if o in driverLocations:
                    trp = Trip(o, d, 0, id, TripType.INTER_A, 0.0, 1.0)
                    if o not in outlfow_trips:
                        outlfow_trips[o] = {trp}
                    else:
                        outlfow_trips[o].add(trp)
                    if d not in inflow_trips:
                        inflow_trips[d] = {trp}
                    else:
                        inflow_trips[d].add(trp)
                    driver_home_trips.add(trp)
                    id += 1
                    ar[(o, d)] = trp
                elif d in driverLocations:
                    trp = Trip(o, d, 0, id, TripType.INTER_B, 0.0, 1.0)
                    if o not in outlfow_trips:
                        outlfow_trips[o] = {trp}
                    else:
                        outlfow_trips[o].add(trp)
                    if d not in inflow_trips:
                        inflow_trips[d] = {trp}
                    else:
                        inflow_trips[d].add(trp)
                    driver_home_trips.add(trp)
                    id += 1
                    ar[(o, d)] = trp
                elif d in homes:
                    trp = Trip(o, d, 0, id, TripType.A, 0.0, 1.0)
                    if o not in outlfow_trips:
                        outlfow_trips[o] = {trp}
                    else:
                        outlfow_trips[o].add(trp)
                    if d not in inflow_trips:
                        inflow_trips[d] = {trp}
                    else:
                        inflow_trips[d].add(trp)
                    secondary_trips.add(trp)
                    id += 1
                    ar[(o, d)] = trp
                elif d in not_homes:
                    trp = Trip(o, d, 0, id, TripType.C, 0.0, 1.0)
                    if o not in outlfow_trips:
                        outlfow_trips[o] = {trp}
                    else:
                        outlfow_trips[o].add(trp)
                    if d not in inflow_trips:
                        inflow_trips[d] = {trp}
                    else:
                        inflow_trips[d].add(trp)
                    secondary_trips.add(trp)
                    id += 1
                    ar[(o, d)] = trp
                if trp is None: exit(1)
                x.append(mdl.binary_var(name='x' + '_' + str(i) + '_' + str(j)))
                tripdex[(o,d)] = len(x) - 1
                t.append(trp.lp.time)
                c.append(trp.lp.miles)
print(primary_trips)
print(secondary_trips)
exit(0)
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


print("Locataion details")
for i, loc in enumerate(locations):
    print("Location", i, loc)

# Constraints
"""
Each Node Visited Once
"""
for j in P + D:
    total = 0
    for intrip in inflow_trips[j]:
        print((intrip.lp.o, intrip.lp.d))
        total += x[tripdex[(intrip.lp.o, intrip.lp.d)]]
    mdl.add_constraint(total == 1, "Primary Location Entered " + j)

for i in P + D:
    total = 0
    for otrip in outlfow_trips[i]:
        print((otrip.lp.o, otrip.lp.d))
        total += x[tripdex[(otrip.lp.o, otrip.lp.d)]]
    mdl.add_constraint(total == 1, "Primary Location Exited " + i)

"""
Time Consistency
"""

for i, o in enumerate(N):
    for j, d in enumerate(N):
        if o != d:
            mdl.add_constraint(ct= B[j] >= B[i] + t[tripdex[(o,d)]] - BIGM*(1- x[tripdex[o,d]]))
            mdl.add_constraint(ct= Q[j] >= Q[i] + q[j] - BIGM*(1- x[tripdex[o,d]]))

"""
Time Windows
"""
for i, loc in enumerate(N):
    mdl.add_constraint(e[i] <= B[i])
    mdl.add_constraint(l[i] >= B[i])

"""
Capacity
"""
for i, loc in enumerate(N):
    mdl.add_constraint(max(0, q[i]) <= Q[i])
    mdl.add_constraint(min(CAP, CAP + q[i]) >= Q[i])

"""
Precedence and Pairing
"""
for i, loc in enumerate(P):
    mdl.add_constraint(B[n + i] >= B[i] + t[tripdex[(loc, N[i + n])]])

for i, loc in enumerate(P):
    mdl.add_constraint(v[i] == v[i + n])

for j, loc in enumerate(N):
    if loc not in driverLocations and loc != N[0]:
        mdl.add_constraint(v[j] >= j * x[tripdex[(N[0], loc)]])
        mdl.add_constraint(v[j] <= j * x[tripdex[(N[0], loc)]] - n * (j * x[tripdex[(N[0], loc)]] - 1))
for i, o in enumerate(N):
    for j, d in enumerate(N):
        if o != d and o not in driverLocations and d not in driverLocations:
            mdl.add_constraint(v[j] >= v[i] + n * (x[tripdex[(o,d)]] - 1))
            mdl.add_constraint(v[j] <= v[i] + n * (1 - x[tripdex[(o,d)]]))

"""
Objective
"""
total = 0.0
for i,v in enumerate(x):
    total += c[i] * v

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
        print(var.get_name() + ": "+ str(var.solution_value))
except Exception as e:
    print(e)
    pass