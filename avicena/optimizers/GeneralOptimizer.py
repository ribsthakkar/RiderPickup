from copy import copy
from docloud.status import JobSolveStatus
from docplex.mp.conflict_refiner import ConflictRefiner, VarLbConstraintWrapper, VarUbConstraintWrapper
from docplex.mp.model import Model
from docplex.mp.relaxer import Relaxer
from docplex.mp.utils import DOcplexException

from avicena.models import Trip, Location
from avicena.optimizers.solver_util.cplex.Listeners import GapListener, TimeListener
from avicena.util.Exceptions import InvalidTripException
from avicena.util.Geolocator import find_coord_lat_lon
from avicena.util.ParserUtil import convert_time
from avicena.util.TimeWindows import get_time_window_by_hours_minutes


class GeneralOptimizer:
    def __init__(self, trips, drivers, name, date, speed, config):
        self.drivers_inp = drivers
        self.trips_inp = trips
        self.date = date
        self.mdl = Model(name=name)
        self.mdl.parameters.randomseed = config['seed']
        self.drivers = list()  # List of all Drivers
        self.primary_trips = dict() # Map Primary trip pair to trip object
        self.all_trips = dict()  # Maps Trip-ID to Trip Object
        self.driver_nodes = set()  # All Driver Nodes
        self.driver_starts = set()  # Starting Nodes of Drivers
        self.driver_ends = set()  # Ending Nodes of Drivers

        self.request_nodes = set()  # Nodes of request trips
        self.request_starts = set()  # Starting nodes of request trips
        self.request_ends = set()  # Ending nodes of request trips
        self.request_map = dict()  # Map from request start to request end
        self.node_capacities = dict()  # Map from node to capacity delta
        self.node_window_open = dict()  # Earliest departure time from a node
        self.node_window_close = dict()  # earliest arrival time to a node
        self.location_to_primary_trip_id_map = dict()  # Map from starting location to ID of primary trip from that location
        self.merges = dict()  # Map from merge trip to incoming primary trip
        self.revenues = dict() # Map from start node to revenue of the trip
        self.wheelchair_locations = set() # Set of locations where wheelchair trips start

        # Decision Variable Structures
        self.trip_vars = dict()  # Map from driver to map of trip to model variable
        self.time_vars = dict()  # Map from driver to map of trip to model variable
        self.capacity_vars = dict()  # Map from driver to map of trip to model variable
        self.revenue_vars = dict()  # Map from driver to revenue variable
        self.wheelchair_vars = dict()  # Map from wheel chair drivers to number of wheelchair trips variable

        # Additional Structures
        self.intrips = dict()  # Map from driver to Map from location to list of incoming trips to that location
        self.outtrips = dict()  # Map from driver to Map from location to list of outgoing trips from that location

        # Constants
        self.SPEED = speed
        self.TRIPS_TO_DO = config["trips_to_do"]
        self.NUM_DRIVERS = config["num_drivers"]
        self.EARLY_PICK_WINDOW = get_time_window_by_hours_minutes(0, config["early_pickup_window"])
        self.EARLY_DROP_WINDOW = get_time_window_by_hours_minutes(0, config["late_pickup_window"])
        self.LATE_PICK_WINDOW = get_time_window_by_hours_minutes(0, config["early_drop_window"])
        self.LATE_DROP_WINDOW = get_time_window_by_hours_minutes(0, config["late_drop_window"])
        self.CAP = config["driver_capacity"]
        self.ROUTE_LIMIT = config["route_limit"]
        self.ROUTE_LIMIT_PEN = config["route_limit_penalty"]
        self.EARLY_DAY_TIME = convert_time(config["early_day_time"])
        self.MERGE_PEN = config["merge_penalty"]
        self.REVENUE_PEN = config["revenue_penalty"]
        self.W_PEN = config["wheelchair_penalty"]

        self.STAGE1_TIME = config["stage1_time"]
        self.STAGE1_GAP = config["stage1_gap"]
        self.STAGE2_TIME = config["stage2_time"]
        self.STAGE2_GAP = config["stage2_gap"]
        self.MAX_RETRIES = config["max_retries"]

        # Prepare Model
        self.obj = 0.0
        self.constraintsToRem = set()
        self.ed_constr = set()
        self.__prepare_trip_parameters()
        self.__prepare_driver_parameters()
        self.__generate_variables()
        self.__prepare_constraints()
        self.__prepare_objective()

    def filter_driver_feasible_trips(self, driver, iter):
        return filter(lambda t: not ((t.lp.o in self.driver_nodes and t.lp.o.get_clean_address() != driver.get_clean_address()) or (
                t.lp.d in self.driver_nodes and t.lp.d.get_clean_address() != driver.get_clean_address()))
                                and t.required_level_of_service in driver.level_of_service
                                and not (abs(self.node_capacities[t.lp.o] + self.node_capacities[t.lp.d]) > driver.capacity), iter)

    def __prepare_trip_parameters(self):
        count = 0
        for index, trip in enumerate(self.trips_inp):
            start = trip.lp.o
            end = trip.lp.d
            pick_time = trip.scheduled_pickup
            drop_time = trip.scheduled_dropoff
            cap = trip.space
            id = trip.id
            rev = trip.rev
            self.request_starts.add(start)
            self.request_ends.add(end)
            self.request_map[start] = end
            if trip.required_level_of_service == 'W': self.wheelchair_locations.add(start)
            a = len(self.request_nodes)
            self.request_nodes.add(start)
            if a == len(self.request_nodes):
                print(start, end)
                exit(1)
            b = len(self.request_nodes)
            self.request_nodes.add(end)
            if b == len(self.request_nodes):
                print(start, end)
                exit(1)
            self.node_capacities[start] = cap
            self.node_capacities[end] = -cap
            self.node_window_close[start] = pick_time + self.LATE_PICK_WINDOW
            self.node_window_open[start] = pick_time - self.EARLY_PICK_WINDOW
            self.node_window_close[end] = drop_time + self.LATE_DROP_WINDOW
            self.node_window_open[end] = pick_time - self.EARLY_PICK_WINDOW + trip.lp.time
            self.all_trips[id] = trip
            self.primary_trips[(start, end)] = trip
            self.location_to_primary_trip_id_map[start] = trip.id
            self.revenues[start] = rev
            self.revenues[end] = 0
            if start not in self.outtrips:
                self.outtrips[start] = {trip}
            else:
                self.outtrips[start].add(trip)
            if end not in self.intrips:
                self.intrips[end] = {trip}
            else:
                self.intrips[end].add(trip)
            count += 1
            if trip.is_merge:
                if 'B' in trip.id:
                    self.merges[trip] = self.all_trips[trip.id[:-1] + 'A']
                elif 'C' in trip.id:
                    self.merges[trip] = self.all_trips[trip.id[:-1] + 'B']
                else:
                    print("Unexpected Trip ID", trip.id)
                    exit(1)
            if count == self.TRIPS_TO_DO:
                break
        print("Number of Trips:", count)

    def __prepare_driver_parameters(self):
        count = 0
        for driver in self.drivers_inp:
            d = copy(driver)
            self.drivers.append(d)
            d.capacity = self.CAP
            start = Location(d.address, find_coord_lat_lon(d.get_clean_address()), d.suffix_len)
            end = Location(d.address, find_coord_lat_lon(d.get_clean_address()), d.suffix_len)
            self.driver_nodes.add(start)
            self.driver_nodes.add(end)
            self.driver_starts.add(start)
            self.driver_ends.add(end)
            self.node_capacities[start] = 0
            self.node_capacities[end] = 0
            self.revenues[start] = 0
            count += 1
            if count == self.NUM_DRIVERS:
                break
        print("Number of Drivers:", count)

    def __generate_variables(self):
        id = 1
        """
        Trips from Driver Start locations to Start location of any request
        """
        for dS in self.driver_starts:
            for rS in self.request_starts:
                t = Trip(dS, rS, 0, id, 0.0, 1.0, self.SPEED, False, 0.0)
                if dS not in self.outtrips:
                    self.outtrips[dS] = {t}
                else:
                    self.outtrips[dS].add(t)
                if rS not in self.intrips:
                    self.intrips[rS] = {t}
                else:
                    self.intrips[rS].add(t)
                id += 1
                self.all_trips[id] = t

        """
        Trips for End location of any request to Driver End locations
        """
        for dE in self.driver_ends:
            for rE in self.request_ends:
                t = Trip(rE, dE, 0, id, 0.0, 1.0, self.SPEED, False, 0.0)
                if rE not in self.outtrips:
                    self.outtrips[rE] = {t}
                else:
                    self.outtrips[rE].add(t)
                if dE not in self.intrips:
                    self.intrips[dE] = {t}
                else:
                    self.intrips[dE].add(t)
                id += 1
                self.all_trips[id] = t

        """
        Trips from any request location to any other request location
        """
        for rS in self.request_nodes:
            for rE in self.request_nodes:
                if rS == rE or (rS in self.request_map and self.request_map[rS] == rE) or (
                        rE in self.request_map and self.request_map[rE] == rS):
                    continue
                try:
                    space = 0
                    if rS in self.wheelchair_locations: space = 1.5
                    t = Trip(rS, rE, space, id, self.node_window_open[rS], self.node_window_close[rE], self.SPEED, False, 0.0)
                except InvalidTripException:
                    # print(rS, rE, nodeDeps[rS], nodeArrs[rE])
                    continue
                if rS not in self.outtrips:
                    self.outtrips[rS] = {t}
                else:
                    self.outtrips[rS].add(t)
                if rE not in self.intrips:
                    self.intrips[rE] = {t}
                else:
                    self.intrips[rE].add(t)
                id += 1
                self.all_trips[id] = t

        """
        Create Decision Variables for Each Driver
        """
        for d in self.drivers:
            self.trip_vars[d] = dict()
            self.time_vars[d] = dict()
            self.capacity_vars[d] = dict()
            for t in self.filter_driver_feasible_trips(d, self.all_trips.values()):
                self.trip_vars[d][t] = self.mdl.binary_var(name='y' + '_' + str(d.id) + '_' + str(t.id))
                self.time_vars[d][t] = self.mdl.continuous_var(lb=0, ub=1, name='t' + '_' + str(d.id) + '_' + str(t.id))
                self.mdl.add_constraint(self.time_vars[d][t] - self.trip_vars[d][t] <= 0)
                self.capacity_vars[d][t] = self.mdl.continuous_var(lb=0, ub=d.capacity, name='q' + '_' + str(d.id) + '_' + str(t.id))
                self.mdl.add_constraint(self.capacity_vars[d][t] - self.trip_vars[d][t] * d.capacity <= 0)


        with open("time.csv", "w") as t, open("cost.csv", "w") as c:
            t.write("Start,End,Time")
            c.write("Start,End,Cost")
            for pair, trp in self.primary_trips.items():
                t.write(pair[0].get_clean_address() + "," + pair[1].get_clean_address() + "," + str(trp.lp.time) + "\n")
                c.write(pair[0].get_clean_address() + "," + pair[1].get_clean_address() + "," + str(trp.lp.miles) + "\n")

    def __prepare_constraints(self):
        """
        Request Requirements
        """
        for trp in self.all_trips:
            if isinstance(trp, str):
                total = 0
                for d in self.drivers:
                    if self.all_trips[trp].required_level_of_service in d.level_of_service:
                        total += self.trip_vars[d][self.all_trips[trp]]
                con = self.mdl.add_constraint(ct=total == 1)
                self.constraintsToRem.add(con)

        """
        Flow Conservation
        """
        for rN in self.request_nodes:
            totalin = 0
            totalout = 0
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[rN]):
                    totalin += self.trip_vars[d][intrip]
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[rN]):
                    totalout -= self.trip_vars[d][otrip]
            self.mdl.add_constraint(ct=totalin <= 1, ctname='flowin' + '_' + str(rN)[:5])
            self.mdl.add_constraint(ct=totalout >= -1, ctname='flowout' + '_' + str(rN)[:5])
            self.mdl.add_constraint(ct=totalin + totalout == 0, ctname='flowinout' + '_' + str(rN)[:5])
        for d in self.drivers:
            for dS in self.driver_starts:
                if dS.get_clean_address() != d.get_clean_address():
                    continue
                total = 0
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[dS]):
                    total -= self.trip_vars[d][otrip]
                self.mdl.add_constraint(ct=total == -1, ctname='driverout' + '_' + str(d.id))
        for d in self.drivers:
            for dE in self.driver_ends:
                if dE.get_clean_address() != d.get_clean_address():
                    continue
                total = 0
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[dE]):
                    total += self.trip_vars[d][intrip]
                self.mdl.add_constraint(ct=total == 1, ctname='driverin' + '_' + str(d.id))

        print("Set flow conservation constraints")

        """
        Time Constraints
        """
        for loc in self.request_ends:
            intripSum = 0
            intripTimes = 0
            intripEnds = self.node_window_close[loc]
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    intripSum += self.time_vars[d][intrip]
                    intripTimes += intrip.lp.time * self.trip_vars[d][intrip]
            self.mdl.add_constraint(intripSum + intripTimes <= intripEnds)
        print("Set arrival time constriants")

        for loc in self.request_starts:
            otripSum = 0
            otripEnds = self.node_window_close[loc]
            otripStarts = self.node_window_open[loc]
            for d in self.drivers:
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    otripSum += self.time_vars[d][otrip]
            self.mdl.add_constraint(otripSum >= otripStarts)
            self.mdl.add_constraint(otripSum <= otripEnds)
        print("Set departure time constraints")

        """
        Precedence Constraints
        """
        for trp in self.all_trips:
            if isinstance(trp, str):
                if (trp.endswith('A') and (trp[:-1] + 'B' in self.all_trips)) or (trp.endswith('B') and (trp[:-1] + 'C' in self.all_trips)):
                    main_trip_start = self.all_trips[trp].lp.o
                    main_trip_dest = self.all_trips[trp].lp.d
                    alt_trip_start = None
                    alt_trip_dest = None
                    if trp.endswith('A'):
                        alt_trip_start = self.all_trips[trp[:-1] + "B"].lp.o
                        alt_trip_dest = self.all_trips[trp[:-1] + "B"].lp.d
                    elif trp.endswith('B'):
                        alt_trip_start = self.all_trips[trp[:-1] + "C"].lp.o
                        alt_trip_dest = self.all_trips[trp[:-1] + "C"].lp.d
                    else:
                        print('Invalid trip id ', trp)
                        exit(1)
                    main_trip_o_out = 0
                    for d in self.drivers:
                        for itrip in self.filter_driver_feasible_trips(d, self.outtrips[main_trip_start]):
                            main_trip_o_out += self.time_vars[d][itrip]
                    main_trip_d_in = 0
                    main_trip_d_time_sum = 0
                    for d in self.drivers:
                        for itrip in self.filter_driver_feasible_trips(d, self.intrips[main_trip_dest]):
                            main_trip_d_in += self.time_vars[d][itrip]
                            main_trip_d_time_sum += itrip.lp.time * self.trip_vars[d][itrip]
                    alt_trip_o_out = 0
                    for d2 in self.drivers:
                        for otrip in self.filter_driver_feasible_trips(d2, self.outtrips[alt_trip_start]):
                            alt_trip_o_out += self.time_vars[d2][otrip]
                    alt_trip_d_in = 0
                    for d2 in self.drivers:
                        for otrip in self.filter_driver_feasible_trips(d2, self.outtrips[alt_trip_dest]):
                            alt_trip_d_in += self.time_vars[d2][otrip]
                    self.mdl.add_constraint(main_trip_o_out <= main_trip_d_in)
                    self.mdl.add_constraint(main_trip_d_in + main_trip_d_time_sum <= alt_trip_o_out)
                    self.mdl.add_constraint(alt_trip_o_out <= alt_trip_d_in)
        print("Set primary trip precedence constraints")

        for loc in self.request_nodes:
            insum, osum = 0, 0
            timeSum = 0
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    insum += self.time_vars[d][intrip]
                    timeSum += self.trip_vars[d][intrip] * intrip.lp.time
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    osum += self.time_vars[d][otrip]
            self.mdl.add_constraint(insum + timeSum <= osum)
        print("Set incoming trip before outgoing trip constraints")

        for loc in self.request_nodes:
            total = 0
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    total += d.id * self.trip_vars[d][intrip]
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    total -= d.id * self.trip_vars[d][otrip]
            self.mdl.add_constraint(ct=total == 0)

        for rS in self.request_starts:
            rE = self.request_map[rS]
            total = 0
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[rE]):
                    total += d.id * self.trip_vars[d][intrip]
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[rS]):
                    total -= d.id * self.trip_vars[d][otrip]
            self.mdl.add_constraint(ct=total == 0)
        print("Set incoming driver is the same as outgoing driver constraints")

        """
        Capacity Constraints
        """
        for loc in self.request_nodes:
            incaps = 0
            ocaps = 0
            for d in self.drivers:
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    ocaps += self.capacity_vars[d][otrip]
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    incaps += self.capacity_vars[d][intrip]
            self.mdl.add_constraint(ocaps == incaps + self.node_capacities[loc])
        print("Set capacity value constraints")

        for d in self.drivers:
            for loc in self.driver_starts:
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    self.mdl.add_constraint(ct=self.capacity_vars[d][otrip] == 0)
            for loc in self.driver_ends:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    self.mdl.add_constraint(ct=self.capacity_vars[d][intrip] == 0)
        print("Set initial and final trip capacity constraints")

        self.__add_custom_constraints()

    def __add_custom_constraints(self):
        print("Adding Custom Defined Constraints")

        """
        Route Length Penalty
        """
        for d in self.drivers:
            otime = 0
            itime = 0
            for dS in self.driver_starts:
                if dS.get_clean_address() != d.get_clean_address():
                    continue
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[dS]):
                    otime += self.time_vars[d][otrip]
                break
            for dE in self.driver_ends:
                if dE.get_clean_address() != d.get_clean_address():
                    continue
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[dE]):
                    itime += self.time_vars[d][intrip]
                break
            self.obj += self.ROUTE_LIMIT_PEN * (itime - otime)
            if not d.early_day_flag:
                try:
                    c = self.mdl.add_constraint(otime >= self.EARLY_DAY_TIME)
                    self.ed_constr.add(c)
                    pass
                except DOcplexException as e:
                    if 'trivially' not in e.message:
                        raise e
                    print(itime, otime)
                    print("Can't restrict early day for", d.name)

        """
        Merge Trip Requirements
        """
        for d in self.drivers:
            for mer in self.filter_driver_feasible_trips(d, self.merges):
                self.mdl.add_constraint(ct =self.trip_vars[d][mer] == self.trip_vars[d][self.merges[mer]])
                self.obj += self.MERGE_PEN * (self.time_vars[d][mer] - (self.time_vars[d][self.merges[mer]] + self.merges[mer].lp.time * self.trip_vars[d][mer])) * (24)
        """
        Equalizing Revenue Penalty
        """
        self.rev_max = self.mdl.continuous_var(0)
        self.rev_min = self.mdl.continuous_var(0)
        for d in self.drivers:
            self.revenue_vars[d] = self.mdl.continuous_var(lb=0, name="Revenue" + str(d.id))
            self.mdl.add_constraint(self.revenue_vars[d] == sum(self.revenues[t.lp.o] * self.trip_vars[d][t] for t in self.filter_driver_feasible_trips(d, self.all_trips.values())))
            self.mdl.add_constraint(self.rev_max >= self.revenue_vars[d])
            self.mdl.add_constraint(self.rev_min <= self.revenue_vars[d])
        self.obj += self.REVENUE_PEN * (self.rev_max - self.rev_min)

        """
        Equalizing Wheel Chair Trip Penalty
        """
        self.w_max = self.mdl.continuous_var(0)
        self.w_min = self.mdl.continuous_var(0)
        for d in self.drivers:
            if 'W' not in d.level_of_service: continue
            self.wheelchair_vars[d] = self.mdl.continuous_var(lb=0, name="Wheelchairs" + str(d.id))
            self.mdl.add_constraint(self.wheelchair_vars[d] == sum(self.trip_vars[d][t] for t in filter(lambda x: x.required_level_of_service == 'W', self.filter_driver_feasible_trips(d, self.all_trips.values()))))
            self.mdl.add_constraint(self.w_max >= self.wheelchair_vars[d])
            self.mdl.add_constraint(self.w_min <= self.wheelchair_vars[d])
        self.obj += self.W_PEN * (self.w_max - self.w_min)

    def __prepare_objective(self):
        """
        Objective function
        """
        for d, driver_trips in self.trip_vars.items():
            for t, var in driver_trips.items():
                self.obj += 1440 * t.lp.time * var
        print("Defined Objective Function")
        self.mdl.minimize(self.obj)

    def solve(self, solution_file):
        """TODO: Make this process of retrying solver better!!!"""
        for i in range(self.MAX_RETRIES):
            removed_ed = False
            removed_sr = False
            try:
                pL = TimeListener(self.STAGE1_TIME)
                self.mdl.add_progress_listener(pL)
                first_solve = self.mdl.solve()
                if first_solve and (first_solve.solve_status == JobSolveStatus.FEASIBLE_SOLUTION or first_solve.solve_status == JobSolveStatus.OPTIMAL_SOLUTION):
                    print("First solve status: " + str(self.mdl.get_solve_status()))
                    print("First solve obj value: " + str(self.mdl.objective_value))
                    driverMiles = self.__write_sol(solution_file+'stage1')
                    print("Total Number of trip miles by each driver after stage 1: ")
                    print(driverMiles)
                else:
                    print("Stage 1 Infeasible with ED")
                if not first_solve or first_solve.solve_status == JobSolveStatus.INFEASIBLE_SOLUTION:
                    self.mdl.remove_progress_listener(pL)
                    if self.STAGE1_GAP:
                        pL = GapListener(self.STAGE1_TIME, self.STAGE1_GAP)
                    else:
                        pL = TimeListener(self.STAGE1_TIME)
                    self.mdl.add_progress_listener(pL)
                    print("Relaxing Early Day Constraints")
                    self.mdl.remove_constraints(self.ed_constr)
                    removed_ed = True
                    first_solve = self.mdl.solve()
                    if first_solve and (
                            first_solve.solve_status == JobSolveStatus.FEASIBLE_SOLUTION or first_solve.solve_status == JobSolveStatus.OPTIMAL_SOLUTION):
                        print("First solve status (No ED): " + str(self.mdl.get_solve_status()))
                        print("First solve obj value (No ED): " + str(self.mdl.objective_value))
                        driverMiles = self.__write_sol(solution_file + 'stage1')
                        print("Total Number of trip miles by each driver after stage 1: ")
                        print(driverMiles)
                    else:
                        print("Stage 1 Infeasible without ED as well")
                print("Relaxing single rider requirements constraints")
                self.mdl.remove_constraints(self.constraintsToRem)
                removed_sr = True
                print("Warm starting from single rider constrained solution")
                if first_solve:
                    self.mdl.add_mip_start(first_solve)
                self.mdl.remove_progress_listener(pL)

                if self.STAGE2_GAP:
                    pL = GapListener(self.STAGE2_TIME, self.STAGE2_GAP)
                else:
                    pL = TimeListener(self.STAGE2_TIME)

                self.mdl.add_progress_listener(pL)
                self.mdl.solve()
                print("Final solve status: " + str(self.mdl.get_solve_status()))
                print("Final Obj value: " + str(self.mdl.objective_value))
                print("Min Revenue:", self.rev_min.solution_value)
                print("Max Revenue:", self.rev_max.solution_value)
                print("Min W Trips:", self.w_min.solution_value)
                print("Max W Trips:", self.w_max.solution_value)
            except DOcplexException as e:
                print(e)
                print(str(i) + "th solution did not work...trying again")
                continue
            finally:
                driverMiles = self.__write_sol(solution_file)
                print("Total Number of trip miles by each driver: ")
                print(driverMiles)
                break

    def __write_sol(self, solution_file):
        driverMiles = dict()
        for d, driver_trips in self.trip_vars.items():
            driverMiles[d] = 0
            for t, var in driver_trips.items():
                if self.trip_vars[d][t].solution_value >= 0.1:
                    driverMiles[d] += t.lp.miles

        def tripGen():
            for d, driver_trips in self.trip_vars.items():
                for t, var in driver_trips.items():
                    if t.lp.o not in self.request_starts or var.solution_value != 1:
                        continue
                    yield (d, t)

        def tripGen_debug(d):
            for t, var in self.trip_vars[d].items():
                if var.solution_value != 1:
                    continue
                yield (d, t)

        for dr in self.drivers:
            for d, t in sorted(tripGen_debug(dr), key=lambda x: self.time_vars[x[0]][x[1]].solution_value):
                print(d.name, t.lp.o, t.lp.d, self.time_vars[d][t].solution_value, t.lp.time)

        with open(solution_file, 'w') as output:
            output.write(
                'trip_id,driver_id,driver_name,trip_date,trip_pickup_address,trip_pickup_time,est_pickup_time,trip_dropoff_address,trip_dropoff_time,est_dropoff_time,trip_los,est_miles,est_time,trip_rev\n')
            count = 0
            for d, t in sorted(tripGen(), key=lambda x: self.time_vars[x[0]][x[1]].solution_value):
                count += 1
                end_time = -1
                rE = self.request_map[t.lp.o]
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[rE]):
                    if self.trip_vars[d][intrip].solution_value == 1:
                        end_time = self.time_vars[d][intrip].solution_value + intrip.lp.time
                        if end_time < self.time_vars[d][t].solution_value + t.lp.time:
                            print('Something wrong')
                            print(sum(self.trip_vars[d][intrip].solution_value for intrip in self.filter_driver_feasible_trips(d, self.intrips[rE])))
                            print(rE)
                            print(t.lp.o, t.lp.d)
                            print(intrip.lp.o, intrip.lp.d)
                            print(t.id, self.time_vars[d][t].solution_value, self.time_vars[d][intrip].solution_value, intrip.lp.time)
                        break
                if end_time < 0:
                    print("Something wrong")
                required_end = self.all_trips[self.location_to_primary_trip_id_map[t.lp.o]].scheduled_dropoff
                ptrip = self.all_trips[self.location_to_primary_trip_id_map[t.lp.o]]
                output.write(str(self.location_to_primary_trip_id_map[t.lp.o]) + "," + str(d.id) + "," + str(d.name) + "," + str(self.date) + ",\"" + str(
                    t.lp.o.get_clean_address()) + "\"," + str(t.scheduled_pickup) + "," + str(self.time_vars[d][t].solution_value) + ",\"" +
                             str(rE.get_clean_address()) + "\"," + str(required_end) + "," + str(end_time) + "," +
                             str(t.required_level_of_service) + "," + str(ptrip.lp.miles) + "," + str(ptrip.lp.time) + "," + str(
                    self.revenues[t.lp.o]) + "\n")
        return driverMiles
