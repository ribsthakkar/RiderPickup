from copy import copy
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import geopandas as gpd
# from geopandas import GeoDataFrame
from shapely.geometry import Point, LineString
import matplotlib.pyplot as plt
import adjustText
import plotly.graph_objects as go
import plotly.express as px
import chart_studio.plotly as py
from plotly.subplots import make_subplots

from docplex.mp.model import Model

from Trip import Trip, locations
from listeners import TimeListener, GapListener


class PDWTWOptimizer:
    BIGM = 100000

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
        self.location_pair = set() # Set of tuples of pickup and dropoff pairs
        self.homes = set()  # set of home locations
        self.not_homes = set()  # set of medical office locations
        self.inflow_trips = dict()  # mapping between a location and list of trips ending at the location
        self.outlfow_trips = dict()  # mapping between a location and list of trips starting at the location
        self.trip_map = dict()  # mapping between a location_pair and associated trip
        self.idxes = dict()  # mapping between location and associated
        self.tripdex = dict()  # mapping between location_pair and index of trip in trip time/cost/binary var containers
        self.primaryTID = set()  # set of IDs of primary trips
        self.primaryOIDs = dict() # map from origin location to trip ID
        self.opposingTrip = dict()  # mapping between trip ID and trip

        # Constants
        self.TRIPS_TO_DO = params["TRIPS_TO_DO"]
        self.DRIVER_IDX = params["DRIVER_IDX"]
        self.NUM_DRIVERS = params["NUM_DRIVERS"]
        self.PICK_WINDOW = params["PICKUP_WINDOW"]
        self.DROP_WINDOW = params["DROP_WINDOW"]
        self.CAP = params["DRIVER_CAP"]


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
            self.obj += self.c[i] * yes
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
                self.obj += 1000 * total
                self.mdl.add_constraint(total >= self.NUM_DRIVERS, "Drivers leaving Depot")
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
        print("Number of variables: ", self.mdl.number_of_variables)
        print("Number of constraints: ", self.mdl.number_of_constraints)

    def __generate_trips(self):
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
                        self.c.append(trp.lp.miles)
                    else:
                        trp = Trip(o, d, 0, id, None, 0.0, 1.0, prefix=False, suffix=True)
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
                            print(o, d)
                            exit(1)
                        self.tripdex[(o, d)] = len(self.x) - 1
                        self.t.append(trp.lp.time)
                        self.c.append(trp.lp.miles)
        with open("time.csv", "w") as t, open("cost.csv", "w") as c:
            t.write("Start,End,Time")
            c.write("Start,End,Cost")
            for pair, trp in self.trip_map.items():
                t.write(pair[0]+ "," + pair[1] + "," + str(trp.lp.time))
                c.write(pair[0]+ "," + pair[1] + "," + str(trp.lp.miles))


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
            if 'A' in id:
                self.opposingTrip[id] = trip
            self.primaryTID.add(id)
            if 'B' in id and start == 0:
                last_trip = self.opposingTrip[id[:-1] + 'A']
                start = last_trip.end + (1 / 24)
            self.idxes[o] = count
            self.idxes[d] = self.TRIPS_TO_DO + count
            self.P.append(o)  # Add to Pickups
            self.D.append(d)  # Add to Dropoffs
            Pe.append(start - self.PICK_WINDOW)  # Add to Pickups open window
            De.append(start - self.DROP_WINDOW)  # Add to Dropoffs open window
            Pl.append(end + self.PICK_WINDOW)  # Add to Pickups close window
            Dl.append(end + self.DROP_WINDOW)  # Add to Dropoffs close window
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

            Pv.append(self.mdl.continuous_var(lb=0, name='v_' + str(
                count)))  # Varaible for index of first location on route pickup
            Dv.append(self.mdl.continuous_var(lb=0, name='v_' + str(
                self.TRIPS_TO_DO + count)))  # Varaible for undex of first location on route dropoff
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
            for i, o in enumerate(self.N):
                for j, d in enumerate(self.N):
                    if o != d:
                        var = self.x[self.tripdex[(o, d)]]
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
        #self.__plot_map(sol_file)
        driver_route = dict()
        primary_trip_assignments = dict()

    def visualize(self, sfile, save=False):
        import random
        sol_df = pd.read_csv(sfile)
        driver_ids = list(sol_df['driver_id'].unique())
        def names(idx):
            return "Driver " + str(driver_ids[idx]) + " Route"
        fig = go.Figure()
        all_x = []
        all_y = []
        locations = dict()
        def get_labels(trips):
            data = "<br>".join(
               "0" * (10 - len(str(t.id))) + str(t.id) + "  |  " + str(timedelta(days=self.B[self.idxes[t.lp.o]].solution_value)).split('.')[0] +
                "  |  " + str(int(self.v[self.idxes[t.lp.o]].solution_value)) for t in trips
            )
            return "<b>TripID,             Time,      DriverID </b><br>" + data
        for i, d_id in enumerate(driver_ids):
            points, trips = zip(*self.__get_driver_coords(d_id))
            points = points[1:-1]
            trips = trips[1:-1]
            for idx, point in enumerate(points):
                if point in locations:
                    locations[point].append(trips[idx])
                    locations[point] = list(sorted(locations[point], key=lambda x: self.B[self.idxes[x.lp.o]].solution_value))
                else:
                    locations[point] = [trips[idx]]
        lon, lat = map(list, zip(*locations.keys()))
        labels = [get_labels(locations[k]) for k in locations.keys()]
        depot = Trip(self.driverstart, self.driverstop, 'A', 'ID', None, 0, 1, prefix=False, suffix=True)
        lon.append(depot.lp.c1[1])
        lat.append(depot.lp.c1[0])
        labels.append("Depot")

        for i, d_id in enumerate(driver_ids):
            r = lambda: random.randint(0, 255)
            col = '#%02X%02X%02X' % (r(), r(), r())
            points, _ = zip(*self.__get_driver_coords(d_id))
            x, y = zip(*points)
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
                name= names(i)
            ))

        fig.add_trace(
            go.Scattermapbox(
                lon=lon,
                lat=lat,
                mode='markers',
                marker=go.scattermapbox.Marker(
                    size=9
                ),
                text=labels,
                name="Locations"
            )
        )

        fig.update_mapboxes(zoom = 10, center=go.layout.mapbox.Center(
        lat=np.mean(all_y),
        lon=np.mean(all_x)
        ), style='open-street-map')

        fig.update_layout(
            title_text=self.mdl.name,
            showlegend=True,
        )
        fig.write_html('visualized.html', auto_open=True)

    def __get_driver_coords(self, id):
        def __filterTrips(id):
            def filt(t):
                try:
                    idx = self.tripdex[(t.lp.o, t.lp.d)]
                    idx2 = self.idxes[t.lp.o]
                    return self.x[idx].solution_value == 1 and self.v[idx2].solution_value == id
                except:
                    return False

            return filt

        def __sortTrips(t):
            idx = self.idxes[t.lp.o]
            return self.B[idx].solution_value
        depot = Trip(self.driverstart, self.driverstop, 'A', 'ID', None, 0, 1, prefix=False, suffix=True)
        yield (depot.lp.c1[1], depot.lp.c1[0]), "Depot"

        prev = 0.0
        for trip in sorted(filter(__filterTrips(id), self.trip_map.values()), key=__sortTrips):
            t = copy(trip)
            if self.Q[self.idxes[t.lp.o]].solution_value > prev:
                t.id = self.primaryOIDs[t.lp.o]
            prev = self.Q[self.idxes[t.lp.o]].solution_value
            yield (trip.lp.c1[1], trip.lp.c1[0]), t

        yield (depot.lp.c2[1], depot.lp.c2[0]), "Depot"