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
locations = list()
driverLocations = list()
driverstart = ""
driverstop = ""
location_pair = set()
homes = set()
not_homes = set()
inflow_trips = dict()
outlfow_trips = dict()
ar = dict()
idxes = dict()
tripdex = dict()
TRIPS_TO_DO = 4
DRIVER_IDX = 0
FIFTEEN = 0.01041666666

last_trip = None
P = [] # Pickup locations
D = [] # Dropoff locations

"""
The following varialbes have the prefixes signifying which location they relate to:
P-Pickup
D-Dropoff

Intial and Final Depot should be the same since driver returns home at teh end of the trip
"""
"""
Decision Variables
"""
PQ = [] # Capacity after node j is visited; Length of N
DQ = [] # Capacity after node j is visited; Length of N

PB = [] # time that node j is visited; Length of N
DB = [] # time that node j is visited; Length of N


Pv = [] # index of first node that is visited in the route; Length of N
Dv = [] # index of first node that is visited in the route; Length of N


"""
Parameters
"""
Pe = [] # start window of node j; length of N
De = [] # start window of node j; length of N

Pl = [] # end window of node j; length of N
Dl = [] # end window of node j; length of N

Pq = [] # demand for each location j; length of N
Dq = [] # demand for each location j; length of N

CAP = 2.5
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
        idxes[d] = TRIPS_TO_DO + count
        P.append(o) # Add to Pickups
        D.append(d) # Add to Dropoffs
        Pe.append(start - FIFTEEN/2) # Add to Pickups open window
        De.append(start - FIFTEEN/2) # Add to Dropoffs open window
        Pl.append(end + FIFTEEN/2) # Add to Pickups close window
        Dl.append(end + FIFTEEN/2) # Add to Dropoffs close window
        Pq.append(CAP) # Add to Pickup capacity
        Dq.append(-CAP) # Add to dropoff capacity

        PQ.append(mdl.continuous_var(lb=0, name='Q_'+str(count))) #Varaible for capacity at location pickup
        DQ.append(mdl.continuous_var(lb=0, name='Q_'+str(TRIPS_TO_DO + count))) #Varaible for capacity at location dropoff

        PB.append(mdl.continuous_var(lb=0, ub=1, name='B_' + str(count))) #Varaible for time at location pickup
        DB.append(mdl.continuous_var(lb=0, ub=1, name='B_' + str(TRIPS_TO_DO + count))) #Varaible for time at location dropoff

        Pv.append(mdl.continuous_var(lb=0, name='v_' + str(count))) #Varaible for index of first location on route pickup
        Dv.append(mdl.continuous_var(lb=0, name='v_' + str(TRIPS_TO_DO + count))) #Varaible for undex of first location on route dropoff

        id = row['trip_id']
        if 'A' in id:
            type = TripType.B
            homes.add(o)
            not_homes.add(d)
        else:
            homes.add(d)
            not_homes.add(o)
            type = TripType.D
        locations.append(o)
        locations.append(d)
        t = Trip(o, d, cap, id, type, start, end, False)
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
for index, row in driver_df.iterrows():
    if count  < DRIVER_IDX:
        count += 1
        continue
    cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
    add = row['Address']
    drivers.add(Driver(row['ID'], row['Driver'], add, cap))
    locations.append(add)
    driverstart = add # + "P"
    driverstop = add #+ "D"
    break

# Append all of the arrays together to make data structure
Q = PQ + DQ
B = PB + DB
v = Pv + Dv
N = P + D
e = Pe + De
l = Pl + Dl
q = Pq + Dq
n = len(P)
print(N)
print(e)
print(l)
print(q)

id = 1
x = [] # binary whether trip ij is taken; length of A
t = [] # time of traversing trip ij; length of A
c = [] # cost of traversing trip ij; length of A
for i, o in enumerate(locations):
    for j, d in enumerate(locations):
        if o != d:
            if (o, d) in location_pair:
                if d in not_homes:
                    x.append(mdl.binary_var(name='B:' + o + '->' + d))
                else:
                    x.append(mdl.binary_var(name='D:' + o + '->' + d))
                trp = ar[(o, d)]
                tripdex[(o, d)] = len(x) - 1
                t.append(trp.lp.time)
                c.append(trp.lp.miles)
            else:
                trp = Trip(o, d, 0, id, TripType.INTER_A, 0.0, 1.0, False)
                if o not in outlfow_trips:
                    outlfow_trips[o] = {trp}
                else:
                    outlfow_trips[o].add(trp)
                if d not in inflow_trips:
                    inflow_trips[d] = {trp}
                else:
                    inflow_trips[d].add(trp)
                id += 1
                ar[(o, d)] = trp
                if o == driverstart:
                    x.append(mdl.binary_var(name='InterA:' + o + '->' + d))
                elif d == driverstop:
                    x.append(mdl.binary_var(name='InterB:' + o + '->' + d))
                elif d in homes:
                    x.append(mdl.binary_var(name='A:' + o + '->' + d))
                elif d in not_homes:
                    x.append(mdl.binary_var(name='C:' + o + '->' + d))
                else:
                    # Shouldn't happen
                    print(o,d)
                    exit(1)
                tripdex[(o, d)] = len(x) - 1
                t.append(trp.lp.time)
                c.append(trp.lp.miles)
print(x)
print(t)
print(c)


# Constraints
"""
Each Node Visited Once
"""
for idx, j in enumerate(N):
    total = 0
    for intrip in inflow_trips[j]:
        # print((intrip.lp.o, intrip.lp.d))
        total += x[tripdex[(intrip.lp.o, intrip.lp.d)]]
    if j in driverLocations: continue
    mdl.add_constraint(total == 1, "Primary Location Entered " + j)
for idx, i in enumerate(N):
    total = 0
    for otrip in outlfow_trips[i]:
        # print((otrip.lp.o, otrip.lp.d))
        total += x[tripdex[(otrip.lp.o, otrip.lp.d)]]
    if i in driverLocations: continue
    mdl.add_constraint(total == 1, "Primary Location Exited " + i)

"""
Time Consistency
"""

for i, o in enumerate(N):
    for j, d in enumerate(N):
        if o != d:
            mdl.add_constraint(ct= B[j] >= B[i] + t[tripdex[(o,d)]] - BIGM*(1- x[tripdex[(o,d)]]))
            mdl.add_constraint(ct= Q[j] >= Q[i] + q[j] - BIGM*(1- x[tripdex[(o,d)]]))

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
    mdl.add_constraint(v[j] >= j * x[tripdex[(driverstart, loc)]])
    mdl.add_constraint(v[j] <= j * x[tripdex[(driverstart, loc)]] - n * (x[tripdex[(driverstart, loc)]] - 1))
for i, o in enumerate(N):
    for j, d in enumerate(N):
        if o != d:
            mdl.add_constraint(v[j] >= v[i] + n * (x[tripdex[(o,d)]] - 1))
            mdl.add_constraint(v[j] <= v[i] + n * (1 - x[tripdex[(o,d)]]))

"""
Temporary Validation
"""
# required = {"B:3908 Avenue B, Austin, TX 78751P->835 N Pleasant Valley Rd , Austin , TX 78702D",
#             "InterB:4509 Springdale Rd, Austin, TX 78723D->110 Inner Campus Drive Austin,TX",
#             "C:835 N Pleasant Valley Rd , Austin , TX 78702D->835 N Pleasant Valley Rd , Austin , TX 78702P",
#             "InterB:3908 Avenue B, Austin, TX 78751D->110 Inner Campus Drive Austin,TX",
#             "B:4509 Springdale Rd, Austin, TX 78723P->1030 Norwood Park Blvd , Austin , TX 78753D",
#             "InterA:110 Inner Campus Drive Austin,TX->3908 Avenue B, Austin, TX 78751P",
#             "InterA:110 Inner Campus Drive Austin,TX->4509 Springdale Rd, Austin, TX 78723P",
#             "D:1030 Norwood Park Blvd , Austin , TX 78753P->4509 Springdale Rd, Austin, TX 78723D",
#             "D:835 N Pleasant Valley Rd , Austin , TX 78702P->3908 Avenue B, Austin, TX 78751D",
#             "C:1030 Norwood Park Blvd , Austin , TX 78753D->1030 Norwood Park Blvd , Austin , TX 78753P"}
# for i, var in enumerate(x):
#     if var.get_name() in required:
#         mdl.add_constraint(ct=x[i] == 1)

"""
Objective
"""
total = 0.0
for i,yes in enumerate(x):
    total += c[i] * yes

# print('\n'.join(str(c) for c in mdl.iter_constraints()))


mdl.minimize(total)
mdl.solve()
print("Solve status: " + str(mdl.get_solve_status()))

try:
    print("Obj value: " + str(mdl.objective_value))
except Exception as e:
    print(e)
    pass

try:

    # for var in x:
    #     print(var.get_name() + ": "+ str(var.solution_value))
    for var0, var1, var2, var3 in zip(N, B, Q, v):
        print('"' + var0 + '"' + ';' + str(var1.solution_value) +';' + str(var2.solution_value) + ';'+ str(var3.solution_value))
        # print(var1.get_name() + ": "+ str(var1.solution_value))
        # print(var2.get_name() + ": "+ str(var2.solution_value))
        # print(var3.get_name() + ": "+ str(var3.solution_value))
    count = 0
    for var in x:
        count += 1
        print("'" + var.get_name() + "';" + str(var.solution_value))
    for var in N:
        count += 1
        print(var)
    for var in Q:
        count += 1
        print(var.get_name() + ": " + str(var.solution_value))
    for var in B:
        count += 1
        print(var.get_name() + ": " + str(var.solution_value))
    for var in v:
        count += 1
        print(var.get_name() + ": " + str(var.solution_value))
    print("Number of trips ", count)
except Exception as e:
    print(e)
    pass
print("Ended", datetime.now())
