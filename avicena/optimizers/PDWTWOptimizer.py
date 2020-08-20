import random
from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from docplex.mp.model import Model
from plotly.subplots import make_subplots

from experimental.Trip import Trip, TripType
from experimental.listeners import TimeListener, GapListener


class PDWTWOptimizer:
    BIGM = 100000
    TOLERANCE = 0.0000001

    def __init__(self, trips, drivers, params):
        self.drivers = drivers
        self.trips = trips
        self.mdl = Model(name=params["MODEL_NAME"])

        # Prepare Data Structures
        self.N = []  # List of all locations
        self.P = []  # List of pickup locations
        self.D = []  # List of dropoff locations
        self.Q = []  # Capacity after visitng location
        self.B = []  # Time of servicing location
        self.v = []  # Index of first node visited in route
        self.PuD = []  # Pickup locations followed by dropoff locations
        self.e = []  # Opening window of location
        self.l = []  # Closing window of location
        self.q = []  # Capacity required by each location
        self.x = []  # binary whether trip ij is taken; length of A
        self.t = []  # time of traversing trip ij; length of A
        self.c = []  # cost of traversing trip ij; length of A
        self.r = []  # driver revenue for doing a trip; length of P
        self.merges = []  # binary whether merge trip was satisfied
        self.location_pair = set()  # Set of tuples of pickup and dropoff pairs
        self.homes = set()  # set of home locations
        self.not_homes = set()  # set of medical office locations
        self.inflow_trips = dict()  # mapping between a location and list of trips ending at the location
        self.outlfow_trips = dict()  # mapping between a location and list of trips starting at the location
        self.trip_map = dict()  # mapping between a location_pair and associated trip
        self.idxes = dict()  # mapping between location and associated index
        self.tripdex = dict()  # mapping between location_pair and index of trip in trip time/cost/binary var containers
        self.primaryTID = set()  # set of IDs of primary trips
        self.primaryOIDs = dict()  # map from origin location to primary trip ID
        self.opposingTrip = dict()  # mapping between trip ID and trip
        self.mergeDict = dict()  # Map between origins of two merge trip locations

        # Constants
        self.TRIPS_TO_DO = params["TRIPS_TO_DO"]
        self.DRIVER_IDX = params["DRIVER_IDX"]
        self.MAX_DRIVERS = params["MAX_DRIVERS"]
        self.MIN_DRIVERS = params["MIN_DRIVERS"]
        # self.NUM_DRIVERS = params["NUM_DRIVERS"]
        self.PICK_WINDOW = params["PICKUP_WINDOW"]
        self.DROP_WINDOW = params["DROP_WINDOW"]
        self.EARLY_PICK_WINDOW = params["EARLY_PICKUP_WINDOW"]
        self.EARLY_DROP_WINDOW = params["EARLY_DROP_WINDOW"]
        self.LATE_PICK_WINDOW = params["LATE_PICKUP_WINDOW"]
        self.LATE_DROP_WINDOW = params["LATE_DROP_WINDOW"]
        self.CAP = params["DRIVER_CAP"]
        self.ROUTE_LIMIT = params["ROUTE_LIMIT"]
        self.MERGE_PEN = params["MERGE_PENALTY"]
        self.DRIVER_PEN = params["DRIVER_PEN"]
        self.W_DRIVER_PEN = params["W_DRIVER_PEN"]
        self.MAX_W_DRIVERS = params["MAX_WHEELCHAIR_DRIVERS"]
        self.MIN_W_DRIVERS = params["MIN_WHEELCHAIR_DRIVERS"]
        self.REVENUE_PEN = params["REVENUE_PENALTY"]
        # self.MIN_SPEED = params["MIN_DRIVING_SPEED"]
        # self.MAX_SPEED = params["MAX_DRIVING_SPEED"]
        # self.SPEED_PENALTY = params["SPEED_PENALTY"]

        # Prepare Model
        self.obj = 0.0
        self.__prepare_trip_parameters()
        self.__prepare_depot()
        self.__generate_trips()
        self.__prepare_constraints()
        self.__prepare_objective()

        # Prepare Solver Listener
        if params["MIP_GAP"]:
            pL = GapListener(params["TIME_LIMIT"], params["MIP_GAP"])
        else:
            pL = TimeListener(params["TIME_LIMIT"])
        self.mdl.add_progress_listener(pL)

    def __prepare_objective(self):
        for i, yes in enumerate(self.x):
            # self.obj += self.c[i] * yes
            self.obj += 1440 * self.t[i] * yes
        self.mdl.minimize(self.obj)

    def __prepare_constraints(self):
        # Constraints

        """
        Each Node Visited Once
        """
        for idx, j in enumerate(self.N):
            total = 0
            for intrip in self.inflow_trips[j]:
                # print((intrip.lp.o, intrip.lp.d))
                total += self.x[self.tripdex[(intrip.lp.o, intrip.lp.d)]]
            if j == self.driverstop:
                # print("here")
                # obj += 1000 * total
                # mdl.add_constraint(total == NUM_DRIVERS, "Drivers returning to Depot")
                pass
            else:
                self.mdl.add_constraint(total == 1, "Primary Location Entered " + j)
        for idx, i in enumerate(self.N):
            total = 0
            for otrip in self.outlfow_trips[i]:
                # print((otrip.lp.o, otrip.lp.d))
                total += self.x[self.tripdex[(otrip.lp.o, otrip.lp.d)]]
            if i == self.driverstart:
                # print("here")
                self.obj += self.DRIVER_PEN * (total)
                # self.mdl.add_constraint(total <= self.MAX_DRIVERS)
                self.mdl.add_constraint(total >= self.MIN_DRIVERS, "Drivers leaving Depot")
                in_total = 0
                for intrip in self.inflow_trips[i]:
                    # print((intrip.lp.o, intrip.lp.d))
                    in_total += self.x[self.tripdex[(intrip.lp.o, intrip.lp.d)]]
                self.mdl.add_constraint(total == in_total, "Drivers Returning to Depot")
            else:
                self.mdl.add_constraint(total == 1, "Primary Location Exited " + i)
        """
        Time Consistency
        """
        for i, o in enumerate(self.PuD):
            for j, d in enumerate(self.PuD):
                if o != d:
                    self.mdl.add_constraint(ct=self.B[j] >= self.B[i] + self.t[self.tripdex[(o, d)]] - self.BIGM * (
                            1 - self.x[self.tripdex[(o, d)]]))
                    self.mdl.add_constraint(
                        ct=self.Q[j] >= self.Q[i] + self.q[j] - self.BIGM * (1 - self.x[self.tripdex[(o, d)]]))
        """
        Time Windows
        """
        for i, loc in enumerate(self.PuD):
            self.mdl.add_constraint(self.e[i] <= self.B[i])
            self.mdl.add_constraint(self.l[i] >= self.B[i])
        """
        Capacity
        """
        for i, loc in enumerate(self.PuD):
            self.mdl.add_constraint(max(0, self.q[i]) <= self.Q[i])
            self.mdl.add_constraint(min(self.CAP, self.CAP + self.q[i]) >= self.Q[i])
        """
        Precedence and Pairing
        """
        n = len(self.P)
        for i, loc in enumerate(self.P):
            self.mdl.add_constraint(self.B[n + i] >= self.B[i] + self.t[self.tripdex[(loc, self.PuD[i + n])]])
        for i, loc in enumerate(self.P):
            self.mdl.add_constraint(self.v[i] == self.v[i + n])
        for j, loc in enumerate(self.PuD):
            self.mdl.add_constraint(self.v[j] >= j * self.x[self.tripdex[(self.driverstart, loc)]])
            self.mdl.add_constraint(self.v[j] <= j * self.x[self.tripdex[(self.driverstart, loc)]] - n * (
                    self.x[self.tripdex[(self.driverstart, loc)]] - 1))
        for i, o in enumerate(self.PuD):
            for j, d in enumerate(self.PuD):
                if o != d:
                    self.mdl.add_constraint(self.v[j] >= self.v[i] + n * (self.x[self.tripdex[(o, d)]] - 1))
                    self.mdl.add_constraint(self.v[j] <= self.v[i] + n * (1 - self.x[self.tripdex[(o, d)]]))

        self.__prepare_custom_constraints()

        print("Number of variables: ", self.mdl.number_of_variables)
        print("Number of constraints: ", self.mdl.number_of_constraints)

    def __prepare_custom_constraints(self):
        n = len(self.P) + 1
        """
        Route Length Limitations
        """
        for i, loc1 in enumerate(self.P):
            for j, loc2 in enumerate(self.P):
                if loc1 == loc2 or abs(self.e[i] - self.e[j + len(self.P)]) <= self.ROUTE_LIMIT: continue
                z1 = self.mdl.binary_var(loc1 + loc2 + 'z1')
                z2 = self.mdl.binary_var(loc1 + loc2 + 'z2')
                m = self.v[i]
                y = self.v[j]
                self.mdl.add_constraint(y - m <= -0.5 * z1 + n * z2)
                self.mdl.add_constraint(y - m >= -n * z1 + z2 * 0.5)
                self.mdl.add_constraint(z1 + z2 == 1)

        """
        Merge Trip Binary Var
        """
        for vars in self.merges:
            loc1, tr = self.mergeDict[vars]
            x = vars[0]
            z1 = vars[1]
            z2 = vars[2]
            m = self.v[self.idxes[loc1]]
            y = self.v[self.idxes[tr.lp.o]]
            self.mdl.add_constraint(y - m <= -0.005 * z1 + n * z2)
            self.mdl.add_constraint(y - m >= -n * z1 + z2 * 0.005)
            self.mdl.add_constraint(x + z1 + z2 == 1)
            self.obj += self.MERGE_PEN * (1 - x)

        """
        Binary variables to represent which one of the n indices was set for v
        """
        self.loc_v_binary = {}
        for j, loc2 in enumerate(self.P):
            idx_vars = []
            for k in range(n):
                x = self.v[j]
                var = self.mdl.binary_var(self.primaryOIDs[loc2] + "-TripValue-" + str(k))
                a = k - 0.4
                b = k + 0.4
                delta = self.mdl.binary_var(self.primaryOIDs[loc2] + "-delta-" + str(k))
                self.mdl.add_constraint(x <= a + self.BIGM * delta + self.BIGM * var)
                self.mdl.add_constraint(x >= b - self.BIGM * (1 - delta) - self.BIGM * var)
                self.mdl.add_constraint(x >= a - self.BIGM * (1 - var))
                self.mdl.add_constraint(x <= b + self.BIGM * (1 - var))
                idx_vars.append(var)
            self.mdl.add_constraint(sum(idx_vars) == 1)
            self.loc_v_binary[j] = idx_vars

        """
        Wheelchair Route Limitations
        """
        unique_w_routes = 0
        self.w_route_bin = []
        for k in range(n):
            var = self.mdl.binary_var(str(k) + "WIndexVar")
            tot = 0
            for loc_idx in filter(lambda idx: self.q[idx] == 1.5, self.loc_v_binary):
                tot += self.loc_v_binary[loc_idx][k]
            self.mdl.add_constraint(self.BIGM * var >= tot)
            self.mdl.add_constraint(tot >= var)
            self.w_route_bin.append(var)
            unique_w_routes += var
        # self.mdl.add_constraint(unique_w_routes <= self.MAX_W_DRIVERS)
        self.mdl.add_constraint(unique_w_routes >= self.MIN_W_DRIVERS)
        self.obj += self.W_DRIVER_PEN * (unique_w_routes - self.MIN_W_DRIVERS)

        """
        Equalizing Revenue Penalty
        """
        self.rev_max = self.mdl.continuous_var(0)
        self.rev_min = self.mdl.continuous_var(0)
        self.revens = []
        for k in range(n):
            bin_var = self.mdl.binary_var(str(k) + "RevenueZero")
            tot = sum(self.loc_v_binary[loc_idx][k] * self.r[loc_idx] for loc_idx in self.loc_v_binary)
            # bin_tot = sum(self.loc_v_binary[loc_idx][k] for loc_idx in self.loc_v_binary)
            # self.mdl.add_equivalence(bin_var, bin_tot == 0)
            sum_var = self.mdl.continuous_var(0, name=str(k) + "Revenue")
            self.mdl.add_constraint(bin_var * self.BIGM >= tot)
            self.mdl.add_constraint(tot >= bin_var)
            self.mdl.add_constraint(self.rev_max >= tot)
            self.mdl.add_constraint(tot + (1 - bin_var) * self.BIGM >= self.rev_min)
            self.mdl.add_constraint(sum_var == tot)
            self.revens.append(sum_var)
        self.mdl.add_constraint(self.rev_max >= self.rev_min)
        self.obj += self.REVENUE_PEN * (self.rev_max - self.rev_min)

        """
        Adjustable Speed Penalty
        """
        # self.obj += self.SPEED_PENALTY * (1/self.MIN_SPEED - self.SPEED)

    def __generate_trips(self):
        # self.SPEED = self.mdl.continuous_var(1/80, 1/self.MIN_SPEED, "Speed")
        # print(self.SPEED)
        id = 1
        for i, o in enumerate(self.N):
            for j, d in enumerate(self.N):
                if o != d:
                    if (o, d) in self.location_pair:
                        if d in self.not_homes:
                            self.x.append(self.mdl.binary_var(name='B:' + o + '->' + d))
                            # self.x.append(mdl.binary_var(name=str(id)))
                        else:
                            self.x.append(self.mdl.binary_var(name='D:' + o + '->' + d))
                            # self.x.append(mdl.binary_var(name=str(id)))
                        trp = self.trip_map[(o, d)]
                        self.tripdex[(o, d)] = len(self.x) - 1
                        self.t.append(trp.lp.time)
                        # self.t.append(trp.lp.miles * self.SPEED)
                        self.c.append(trp.lp.miles)
                        if trp.rev <= 0:
                            print("Revenue should be non zero for trip")
                            exit(1)
                        self.r.append(trp.rev)
                    else:
                        trp = Trip(o, d, 0, id, None, 0.0, 1.0, 0.0, prefix=False, suffix=True)
                        if o not in self.outlfow_trips:
                            self.outlfow_trips[o] = {trp}
                        else:
                            self.outlfow_trips[o].add(trp)
                        if d not in self.inflow_trips:
                            self.inflow_trips[d] = {trp}
                        else:
                            self.inflow_trips[d].add(trp)
                        id += 1
                        self.trip_map[(o, d)] = trp
                        if o == self.driverstart:
                            self.x.append(self.mdl.binary_var(name='InterA:' + o + '->' + d))
                        elif d == self.driverstop:
                            self.x.append(self.mdl.binary_var(name='InterB:' + o + '->' + d))
                        elif d in self.homes:
                            self.x.append(self.mdl.binary_var(name='A:' + o + '->' + d))
                        elif d in self.not_homes:
                            self.x.append(self.mdl.binary_var(name='C:' + o + '->' + d))
                        else:
                            # Shouldn't happen
                            print("OD not in main location categories")
                            print(o, d)
                            exit(1)
                        self.tripdex[(o, d)] = len(self.x) - 1
                        self.t.append(trp.lp.time)
                        # self.t.append(trp.lp.miles * self.SPEED)
                        self.c.append(trp.lp.miles)

        with open("time.csv", "w") as t, open("cost.csv", "w") as c:
            t.write("Start,End,Time")
            c.write("Start,End,Cost")
            for pair, trp in self.trip_map.items():
                t.write(pair[0] + "," + pair[1] + "," + str(trp.lp.time))
                c.write(pair[0] + "," + pair[1] + "," + str(trp.lp.miles))

    def __prepare_depot(self):
        self.N.append(self.drivers[self.DRIVER_IDX].address)
        self.driverstart = self.drivers[self.DRIVER_IDX].address
        self.driverstop = self.drivers[self.DRIVER_IDX].address

    def __prepare_trip_parameters(self):
        PQ = []  # Capacity after node j is visited; Length of N
        DQ = []  # Capacity after node j is visited; Length of N
        PB = []  # time that node j is visited; Length of N
        DB = []  # time that node j is visited; Length of N
        Pv = []  # index of first node that is visited in the route; Length of N
        Dv = []  # index of first node that is visited in the route; Length of N
        Pe = []  # start window of node j; length of N
        De = []  # start window of node j; length of N
        Pl = []  # end window of node j; length of N
        Dl = []  # end window of node j; length of N
        Pq = []  # demand for each location j; length of N
        Dq = []  # demand for each location j; length of N
        count = 0
        last_trip = None
        for index, trip in enumerate(self.trips):
            o = trip.lp.o
            d = trip.lp.d
            start = trip.start
            end = trip.end
            cap = trip.space
            id = trip.id
            if 'A' in id:
                self.homes.add(o)
                self.not_homes.add(d)
            else:
                self.homes.add(d)
                self.not_homes.add(o)
            self.N.append(o)
            self.N.append(d)
            self.opposingTrip[id] = trip
            self.primaryTID.add(id)
            self.idxes[o] = count
            self.idxes[d] = self.TRIPS_TO_DO + count
            self.P.append(o)  # Add to Pickups
            self.D.append(d)  # Add to Dropoffs
            Pe.append(start - self.EARLY_PICK_WINDOW)  # Add to Pickups open window
            De.append(start - self.EARLY_DROP_WINDOW)  # Add to Dropoffs open window
            Pl.append(end + self.LATE_PICK_WINDOW)  # Add to Pickups close window
            Dl.append(end + self.LATE_DROP_WINDOW)  # Add to Dropoffs close window
            Pq.append(cap)  # Add to Pickup capacity
            Dq.append(-cap)  # Add to dropoff capacity

            PQ.append(self.mdl.continuous_var(lb=0, name='Q_' + str(count)))  # Varaible for capacity at location pickup
            DQ.append(self.mdl.continuous_var(lb=0, name='Q_' + str(
                self.TRIPS_TO_DO + count)))  # Varaible for capacity at location dropoff

            PB.append(
                self.mdl.continuous_var(lb=0, ub=1, name='B_' + str(count)))  # Varaible for time at location pickup
            DB.append(self.mdl.continuous_var(lb=0, ub=1,
                                              name='B_' + str(
                                                  self.TRIPS_TO_DO + count)))  # Varaible for time at location dropoff

            Pv.append(self.mdl.integer_var(lb=0, ub=len(self.trips) + 1, name='v_' + str(
                count)))  # Varaible for index of first location on route pickup
            Dv.append(self.mdl.integer_var(lb=0, ub=len(self.trips) + 1, name='v_' + str(
                self.TRIPS_TO_DO + count)))  # Varaible for undex of first location on route dropoff
            if trip.type == TripType.MERGE:
                vars = (self.mdl.binary_var(name=trip.id), self.mdl.binary_var(name=trip.id + 'z1'),
                        self.mdl.binary_var(name=trip.id + 'z2'))
                self.merges.append(vars)
                if 'B' in trip.id:
                    self.mergeDict[self.merges[-1]] = (trip.lp.o, self.opposingTrip[trip.id[:-1] + 'A'])
                elif 'C' in trip.id:
                    self.mergeDict[self.merges[-1]] = (trip.lp.o, self.opposingTrip[trip.id[:-1] + 'B'])
                else:
                    print("Unexpected Trip ID", trip.id)
                    exit(1)

            self.primaryOIDs[o] = id
            self.location_pair.add((o, d))
            self.trip_map[(o, d)] = trip
            if o not in self.outlfow_trips:
                self.outlfow_trips[o] = {trip}
            else:
                self.outlfow_trips[o].add(trip)
            if d not in self.inflow_trips:
                self.inflow_trips[d] = {trip}
            else:
                self.inflow_trips[d].add(trip)
            count += 1
            last_trip = trip
            if count == self.TRIPS_TO_DO:
                break
        self.Q = PQ + DQ
        self.B = PB + DB
        self.v = Pv + Dv
        self.PuD = self.P + self.D
        self.e = Pe + De
        self.l = Pl + Dl
        self.q = Pq + Dq

    def solve(self, sol_file):

        self.mdl.solve()
        print("Solve status: " + str(self.mdl.get_solve_status()))

        try:
            print("Obj value: " + str(self.mdl.objective_value))
        except Exception as e:
            print(e)
            pass

        with open(sol_file, 'w') as output:
            output.write(
                'trip_id,driver_id,trip_pickup_address,trip_pickup_time,est_pickup_time,trip_dropoff_adress,trip_dropoff_time,est_dropoff_time,trip_los,est_miles,est_time\n')
            miles = 0
            time = 0
            for i, o in enumerate(self.N):
                for j, d in enumerate(self.N):
                    if o != d:
                        var = self.x[self.tripdex[(o, d)]]
                        miles += var.solution_value * self.c[self.tripdex[(o, d)]]
                        time += var.solution_value * self.t[self.tripdex[(o, d)]]
                        t = self.trip_map[(o, d)]
                        if t.id not in self.primaryTID:
                            continue
                        arrival = self.idxes[o]
                        dep = arrival + self.TRIPS_TO_DO
                        output.write(str(t.id) + "," + str(round(self.v[arrival].solution_value)) + ",\"" + str(
                            t.lp.o[:-4]) + "\"," + str(t.start) + "," + str(self.B[arrival].solution_value) + ",\"" +
                                     str(t.lp.d[:-4]) + "\"," + str(t.end) + "," + str(
                            self.B[dep].solution_value) + "," +
                                     str(t.los) + "," + str(t.lp.miles) + "," + str(t.lp.time) + "\n")
                        # print("'" + var.get_name() + "';" + str(var.solution_value) + ';' + str(t.start) + ';' + str(
                        #     t.end) + ';' + str(t.lp.miles))
        driver_route = dict()
        primary_trip_assignments = dict()
        # for loc_vars in self.w_locs:
        #     for k in range(len(self.P)):
        #         print(k, loc_vars[k].solution_value)
        # for i, var in enumerate(self.revens):
        #     print(i, var.solution_value)
        print("Total Miles Traveled", miles)
        print("Total Minutes Driving", time * 1440)

        print("Max Revenue", self.rev_max.solution_value)
        print("Min Revenue", self.rev_min.solution_value)
        print("Revenue Penalty", self.REVENUE_PEN * (self.rev_max.solution_value - self.rev_min.solution_value))

        driver_pen = 0
        for idx, i in enumerate(self.N):
            total = 0
            for otrip in self.outlfow_trips[i]:
                # print((otrip.lp.o, otrip.lp.d))
                total += self.x[self.tripdex[(otrip.lp.o, otrip.lp.d)]].solution_value
            if i == self.driverstart:
                # print("here")
                driver_pen = self.DRIVER_PEN * (total - self.MIN_DRIVERS)
                break
        print("Additional Driver Penalty", driver_pen)

        w_routes = sum(v.solution_value for v in self.w_route_bin)
        w_pen = self.W_DRIVER_PEN * (w_routes - self.MAX_W_DRIVERS)
        print("Additional Wheelchair Driver Penalty", w_pen)

        m_pen = 0
        for vars in self.merges:
            x = vars[0]
            m_pen += self.MERGE_PEN * (1 - x.solution_value)
        print("Merge Unsatisfaction Penalty", m_pen)

    def visualize(self, sfile, vfile='visualized.html'):
        def names(id):
            return "Driver " + str(id) + " Route"

        def get_labels(trips):
            data = "<br>".join(
                "0" * (10 - len(str(t.id))) + str(t.id) + "  |  " +
                str(timedelta(days=self.B[self.idxes[t.lp.o]].solution_value)).split('.')[0] +
                "  |  " + str(int(self.v[self.idxes[t.lp.o]].solution_value)) for t in trips
            )
            return trips[0].lp.o[:-4] + "<br><b>TripID,             Time,      DriverID </b><br>" + data

        sol_df = pd.read_csv(sfile)
        driver_ids = list(sol_df['driver_id'].unique())
        titles = [names(i) for i in driver_ids]
        titles.insert(0, "Map")
        titles.insert(1, "Driver Summary")
        subplots = [[{"type": "table"}]] * (len(driver_ids) + 1)
        subplots.insert(0, [{"type": "scattermapbox"}])
        map_height = 600 / (600 + 400 * (len(driver_ids) + 1))
        heights = [(1 - map_height - 0.05) / ((len(driver_ids)) + 1)] * (len(driver_ids) + 1)
        heights.insert(0, map_height)
        # heights = [0.25]
        fig = make_subplots(
            rows=2 + len(driver_ids), cols=1,
            vertical_spacing=0.004,
            subplot_titles=titles,
            specs=subplots,
            row_heights=heights
        )
        all_x = []
        all_y = []
        locations = dict()
        # for i, d_id in enumerate(driver_ids[0:1]):
        #     points, trips = zip(*self.__get_driver_coords(d_id))

        for i, d_id in enumerate(driver_ids):
            r = lambda: random.randint(0, 255)
            col = '#%02X%02X%02X' % (r(), r(), r())
            points, trips = zip(*self.__get_driver_coords(d_id))
            x, y = zip(*points)
            filtered_trips = list(filter(lambda t: t.id in self.primaryOIDs.values(), trips))
            details = [[str(t.id) for t in filtered_trips],
                       [t.lp.o[:-4] for t in filtered_trips],
                       [t.lp.d[:-4] for t in filtered_trips],
                       [str(timedelta(days=self.B[self.idxes[t.lp.o]].solution_value)).split('.')[0] for t in
                        filtered_trips],
                       [str(timedelta(days=self.opposingTrip[t.id].start)).split('.')[0] for t in filtered_trips],
                       [str(timedelta(days=self.B[self.idxes[t.lp.o] + self.TRIPS_TO_DO].solution_value)).split('.')[0]
                        for t in filtered_trips],
                       [str(timedelta(days=self.opposingTrip[t.id].end)).split('.')[0] for t in filtered_trips],
                       [str(t.preset_m) for t in filtered_trips],
                       [str(t.los) for t in filtered_trips],
                       [str(t.rev) for t in filtered_trips],
                       ]
            all_x += x
            all_y += y
            fig.add_trace(go.Scattermapbox(
                lon=x,
                lat=y,
                mode='lines',
                marker=dict(
                    size=8,
                    color=col,
                ),
                name=names(d_id),

            ), row=1, col=1)
            fig.add_trace(
                go.Table(
                    header=dict(
                        values=["TripID", "Pickup Address", "Dropoff Address", "Estimated Pickup Time",
                                "Scheduled Pickup Time", "Estimated Dropoff Time", "Scheduled Dropoff Time", "Miles",
                                "LOS", "Revenue"],
                        font=dict(size=10),
                        align="left"
                    ),
                    cells=dict(
                        values=details,
                        align="left")
                ),
                row=i + 3, col=1,
            )
            points = points[1:-1]
            trips = trips[1:-1]
            for idx, point in enumerate(points):
                if point in locations:
                    locations[point].append(trips[idx])
                    locations[point] = list(
                        sorted(locations[point], key=lambda x: self.B[self.idxes[x.lp.o]].solution_value))
                else:
                    locations[point] = [trips[idx]]

        lon, lat = map(list, zip(*locations.keys()))
        labels = [get_labels(locations[k]) for k in locations.keys()]
        depot = Trip(self.driverstart, self.driverstop, 'A', 'ID', None, 0, 1, prefix=False, suffix=True)
        lon.append(depot.lp.c1[1])
        lat.append(depot.lp.c1[0])
        labels.append(self.driverstart + "<br>Depot")

        fig.add_trace(
            go.Scattermapbox(
                lon=lon,
                lat=lat,
                mode='markers',
                marker=go.scattermapbox.Marker(
                    size=9
                ),
                text=labels,
                name="Locations",

            ),
            row=1, col=1
        )
        ids, times, miles, rev = zip(*(self.__get_driver_trips_times_miles_rev(id) for id in driver_ids))
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Driver", "Trips", "Time", "Miles", "Revenue"],
                    font=dict(size=10),
                    align="left"
                ),
                cells=dict(
                    values=[driver_ids, ids, times, miles, rev],
                    align="left")
            ),
            row=2, col=1,
        )

        fig.update_mapboxes(zoom=10, center=go.layout.mapbox.Center(
            lat=np.mean(all_y),
            lon=np.mean(all_x)), style='open-street-map')

        fig.update_layout(
            title_text=self.mdl.name,
            showlegend=True,
            height=(600 + 400 * (len(driver_ids) + 1))
        )
        fig.write_html(vfile, auto_open=True)

    def __filterTrips(self, id):
        def filt(t):
            try:
                idx = self.tripdex[(t.lp.o, t.lp.d)]
                idx2 = self.idxes[t.lp.o]
                return self.x[idx].solution_value == 1 and int(round(self.v[idx2].solution_value)) == id
            except:
                idx = self.tripdex[(t.lp.o, t.lp.d)]
                idx2 = self.idxes[t.lp.d]
                return self.x[idx].solution_value == 1 and int(round(self.v[idx2].solution_value)) == id

        return filt

    def __filterPrimaryTrips(self, id):
        def filt(t):
            if t.id not in self.primaryTID:
                return False
            idx2 = self.idxes[t.lp.o]
            return int(round(self.v[idx2].solution_value)) == id

        return filt

    def __sortTrips(self, t):
        try:
            idx = self.idxes[t.lp.o]
            return self.B[idx].solution_value
        except:
            return 0.000000001

    def __get_driver_coords(self, id):
        depot = Trip(self.driverstart, self.driverstop, 'A', 'ID', None, 0, 1, prefix=False, suffix=True)
        prev = 0.0
        for trip in sorted(filter(self.__filterTrips(id), self.trip_map.values()), key=self.__sortTrips):
            t = Trip(trip.lp.o, trip.lp.d, 1 if trip.los == 'A' else 1.5, trip.id, None, trip.start, trip.end, rev=0.0,
                     lp=trip.lp)
            # if t.lp.o != self.driverstart and self.Q[self.idxes[t.lp.o]].solution_value - prev > 0.1 and t.lp.d != self.driverstop:
            if t.lp.o in self.primaryOIDs:
                try:
                    t.id = self.primaryOIDs[t.lp.o]
                    t.lp.d = self.opposingTrip[t.id].lp.d
                    t.rev = self.r[self.idxes[t.lp.o]]
                except:
                    print("Failed to get primary origin ID", t.id, t.lp.o, t.lp.d,
                          self.Q[self.idxes[t.lp.o]].solution_value, prev)
                    exit(1)
                prev = self.Q[self.idxes[t.lp.o]].solution_value
            yield (t.lp.c1[1], t.lp.c1[0]), t
        yield (depot.lp.c2[1], depot.lp.c2[0]), depot

    def __get_driver_trips_times_miles_rev(self, id):
        return ", ".join(map(lambda t: str(t.id), filter(self.__filterPrimaryTrips(id), self.trip_map.values()))), \
               str(timedelta(
                   days=sum(t.lp.time for t in filter(self.__filterTrips(id), self.trip_map.values())))).split('.')[0], \
               str(sum(t.lp.miles for t in filter(self.__filterTrips(id), self.trip_map.values()))), \
               str(sum(t.rev for t in filter(self.__filterPrimaryTrips(id), self.trip_map.values())))
