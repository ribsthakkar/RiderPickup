from copy import copy

from docplex.mp.model import Model
from docplex.mp.utils import DOcplexException

from Trip import Trip, locations, InvalidTripException
from listeners import TimeListener, GapListener

class GeneralOptimizer:
    def filtered(self, d, iter):
        return filter(lambda t: not ((t.lp.o in self.driverNodes and t.lp.o[:4] != d.address[:4]) or (
                    t.lp.d in self.driverNodes and t.lp.d[:4] != d.address[:4])) and t.los in d.los
                                and not (abs(self.nodeCaps[t.lp.o] + self.nodeCaps[t.lp.d]) > d.capacity), iter)


    def __init__(self, trips, drivers, params):
        self.drivers_inp = drivers
        self.trips_inp = trips
        self.mdl = Model(name=params["MODEL_NAME"])

        self.drivers = list()  # List of all Drivers
        self.primary_trips = dict() # Map Primary trip pair to trip object
        self.all_trips = dict()  # Maps Trip-ID to Trip Object
        self.driverNodes = set()  # All Driver Nodes
        self.driverStart = set()  # Starting Nodes of Driver
        self.driverEnd = set()  # Ending Nodes of Driver

        self.requestNodes = set()  # Nodes of request trips
        self.requestStart = set()  # Starting nodes of request trips
        self.requestEnd = set()  # Ending nodes of request trips
        self.requestPair = dict()  # Map from request start to request end
        self.nodeCaps = dict()  # Map from node to capacity delta
        self.nodeDeps = dict()  # Earliest departure time from a node
        self.nodeArrs = dict()  # earliest arrival time to a node
        self.primaryTID = dict()  # Map from starting location to ID of primary trip from that location

        # Decision Variable Structures
        self.trips = dict()  # Map from driver to map of trip to model variable
        self.times = dict()  # Map from driver to map of trip to model variable
        self.caps = dict()  # Map from driver to map of trip to model variable

        # Additional Structures
        self.intrips = dict()  # Map from driver to Map from location to list of trips
        self.outtrips = dict()  # Map from driver to Map from location to list of trips

        # Constants
        self.TRIPS_TO_DO = params["TRIPS_TO_DO"]
        self.DRIVER_IDX = params["DRIVER_IDX"]
        self.NUM_DRIVERS = params["NUM_DRIVERS"]
        self.PICK_WINDOW = params["PICKUP_WINDOW"]
        self.DROP_WINDOW = params["DROP_WINDOW"]
        self.CAP = params["DRIVER_CAP"]

        self.STAGE1_TIME = params["STAGE1_TIME"]
        self.STAGE1_GAP = params["STAGE1_GAP"]
        self.STAGE2_TIME = params["STAGE1_TIME"]
        self.STAGE2_GAP = params["STAGE1_GAP"]
        self.MIP_GAP = params["MIP_GAP"]
        self.TIME_LIMIT = params["TIME_LIMIT"]

        # Prepare Model
        self.obj = 0.0
        self.__prepare_trip_parameters()
        self.__prepare_driver_parameters()
        self.__generate_trips()
        self.__prepare_constraints()
        self.__prepare_objective()



    def __prepare_trip_parameters(self):
        count = 0
        for index, trip in enumerate(self.trips_inp):
            start = trip.lp.o
            end = trip.lp.d
            pick = trip.start
            drop = trip.end
            cap = trip.space
            id = trip.id
            self.requestStart.add(start)
            self.requestEnd.add(end)
            self.requestPair[start] = end
            a = len(self.requestNodes)
            self.requestNodes.add(start)
            if a == len(self.requestNodes):
                print(start, end)
                exit(1)
            b = len(self.requestNodes)
            self.requestNodes.add(end)
            if b == len(self.requestNodes):
                print(start, end)
                exit(1)
            self.nodeCaps[start] = cap
            self.nodeCaps[end] = -cap
            self.nodeArrs[start] = drop - trip.lp.time  # 0
            self.nodeDeps[start] = pick  # max(0, pick - BUFFER)
            self.nodeArrs[end] = drop
            self.nodeDeps[end] = pick + trip.lp.time  # 0 # max(0, pick - BUFFER) + t.lp.time
            self.all_trips[id] = trip
            self.primary_trips[(start,end)] = trip
            self.primaryTID[start] = trip.id
            if start not in self.outtrips:
                self.outtrips[start] = {trip}
            else:
                self.outtrips[start].add(trip)
            if end not in self.intrips:
                self.intrips[end] = {trip}
            else:
                self.intrips[end].add(trip)
            count += 1
            if count == self.TRIPS_TO_DO:
                break

    def __prepare_driver_parameters(self):
        count = 0
        for driver in self.drivers_inp:
            d = copy(driver)
            self.drivers.append(d)
            d.capacity = 2
            start = str(hash(d.id))[:0] + "Or:" + d.address
            end = str(hash(d.id))[:0] + "De:" + d.address
            self.driverNodes.add(start)
            self.driverNodes.add(end)
            self.driverStart.add(start)
            self.driverEnd.add(end)
            self.nodeCaps[start] = 0
            self.nodeCaps[end] = 0

            count += 1
            if count == self.NUM_DRIVERS:
                break
        print("Number of Drivers:", count)

    def __generate_trips(self):
        id = 1
        """
        Trips from Driver Start locations to Start location of any request
        """
        for dS in self.driverStart:
            for rS in self.requestStart:
                t = Trip(dS, rS, 0, id, None, 0.0, 1.0, prefix=True)
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
        for dE in self.driverEnd:
            for rE in self.requestEnd:
                t = Trip(rE, dE, 0, id, None, 0.0, 1.0, prefix=True)
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
        for rS in self.requestNodes:
            for rE in self.requestNodes:
                if rS == rE or (rS in self.requestPair and self.requestPair[rS] == rE) or (
                        rE in self.requestPair and self.requestPair[rE] == rS):
                    continue
                try:
                    t = Trip(rS, rE, 0, id, None, self.nodeDeps[rS], self.nodeArrs[rE], prefix=True)
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
            self.trips[d] = dict()
            self.times[d] = dict()
            self.caps[d] = dict()
            for t in self.filtered(d, self.all_trips.values()):
                self.trips[d][t] = self.mdl.binary_var(name='y' + '_' + str(d.id) + '_' + str(t.id))
                self.times[d][t] = self.mdl.continuous_var(lb=0, ub=1, name='t' + '_' + str(d.id) + '_' + str(t.id))
                self.mdl.add_constraint(self.times[d][t] - self.trips[d][t] <= 0)
                self.caps[d][t] = self.mdl.continuous_var(lb=0, ub=d.capacity, name='q' + '_' + str(d.id) + '_' + str(t.id))
                self.mdl.add_constraint(self.caps[d][t] - self.trips[d][t] * d.capacity <= 0)


        with open("time.csv", "w") as t, open("cost.csv", "w") as c:
            t.write("Start,End,Time")
            c.write("Start,End,Cost")
            for pair, trp in self.primary_trips.items():
                t.write(pair[0]+ "," + pair[1] + "," + str(trp.lp.time))
                c.write(pair[0]+ "," + pair[1] + "," + str(trp.lp.miles))


    def __prepare_constraints(self):
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
        self.constraintsToRem = set()
        for trp in self.all_trips:
            if isinstance(trp, str):
                total = 0
                for d in self.drivers:
                    if self.all_trips[trp].los in d.los:
                        total += self.trips[d][self.all_trips[trp]]
                con = self.mdl.add_constraint(ct=total == 1)
                self.constraintsToRem.add(con)
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
        for rN in self.requestNodes:
            totalin = 0
            totalout = 0
            for d in self.drivers:
                for intrip in self.filtered(d, self.intrips[rN]):
                    totalin += self.trips[d][intrip]
                for otrip in self.filtered(d, self.outtrips[rN]):
                    totalout -= self.trips[d][otrip]
            self.mdl.add_constraint(ct=totalin <= 1, ctname='flowin' + '_' + str(rN)[:5])
            self.mdl.add_constraint(ct=totalout >= -1, ctname='flowout' + '_' + str(rN)[:5])
            self.mdl.add_constraint(ct=totalin + totalout == 0, ctname='flowinout' + '_' + str(rN)[:5])
        for d in self.drivers:
            for dS in self.driverStart:
                if dS[3:] != d.address:
                    continue
                total = 0
                for otrip in self.filtered(d, self.outtrips[dS]):
                    total -= self.trips[d][otrip]
                self.mdl.add_constraint(ct=total == -1, ctname='driverout' + '_' + str(d.id))
        for d in self.drivers:
            for dE in self.driverEnd:
                if dE[3:] != d.address:
                    continue
                total = 0
                for intrip in self.filtered(d, self.intrips[dE]):
                    total += self.trips[d][intrip]
                self.mdl.add_constraint(ct=total == 1, ctname='driverin' + '_' + str(d.id))

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
        for loc in self.requestNodes:
            intripSum = 0
            intripTimes = 0
            intripEnds = self.nodeArrs[loc]
            for d in self.drivers:
                for intrip in self.filtered(d, self.intrips[loc]):
                    intripSum += self.times[d][intrip]
                    intripTimes += intrip.lp.time * self.trips[d][intrip]
                    # intripEnds += intrip.end * trips[d][intrip]
            self.mdl.add_constraint(intripSum + intripTimes <= intripEnds)
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
        for loc in self.requestNodes:
            otripSum = 0
            otripStarts = self.nodeDeps[loc]
            for d in self.drivers:
                for otrip in self.filtered(d, self.outtrips[loc]):
                    otripSum += self.times[d][otrip]
                    # otripStarts += otrip.start * trips[d][otrip]
                # obj += pickupEarlyPenalty * (otripStarts - (otripSum + BUFFER))
                # obj += pickupLatePenalty * (otripStarts - (otripSum - BUFFER))
            self.mdl.add_constraint(otripSum + self.PICK_WINDOW >= otripStarts)
            self.mdl.add_constraint(otripSum <= otripStarts + self.PICK_WINDOW)
        print("Set departure time constraints")

        """
        Precedence Constraints
        """
        for trp in self.all_trips:
            if isinstance(trp, str):
                if trp.endswith('A') and (trp[:-1] + 'B') in self.all_trips:
                    main_trip = self.all_trips[trp]
                    main_trip_loc = self.all_trips[trp].lp.d
                    alt_trip_loc = self.all_trips[trp[:-1] + "B"].lp.o
                    isum = 0
                    itimeSum = 0
                    for d in self.drivers:
                        for intrip in self.filtered(d, self.intrips[main_trip_loc]):
                            isum += self.times[d][intrip]
                            itimeSum += intrip.lp.time * self.trips[d][intrip]
                    osum = 0
                    for d2 in self.drivers:
                        for otrip in self.filtered(d2, self.outtrips[alt_trip_loc]):
                            osum += self.times[d2][otrip]
                            # print(d.id, d2.id, repr(intrip), repr(otrip))
                            # mdl.add_indicator(trips[d][intrip], times[d][intrip] + intrip.lp.time <= times[d2][otrip])
                    self.mdl.add_constraint(isum + itimeSum <= osum)
        print("Set primary trip precedence constraints")

        for loc in self.requestNodes:
            insum, osum = 0, 0
            timeSum = 0
            for d in self.drivers:
                for intrip in self.filtered(d, self.intrips[loc]):
                    insum += self.times[d][intrip]
                    timeSum += self.trips[d][intrip] * intrip.lp.time
                for otrip in self.filtered(d, self.outtrips[loc]):
                    osum += self.times[d][otrip]
            self.mdl.add_constraint(insum + timeSum <= osum)
        print("Set incoming trip before outgoing trip constraints")

        for loc in self.requestNodes:
            total = 0
            for d in self.drivers:
                for intrip in self.filtered(d, self.intrips[loc]):
                    total += d.id * self.trips[d][intrip]
                for otrip in self.filtered(d, self.outtrips[loc]):
                    total -= d.id * self.trips[d][otrip]
            self.mdl.add_constraint(ct=total == 0)

        for rS in self.requestStart:
            rE = self.requestPair[rS]
            total = 0
            for d in self.drivers:
                for intrip in self.filtered(d, self.intrips[rE]):
                    total += d.id * self.trips[d][intrip]
                for otrip in self.filtered(d, self.outtrips[rS]):
                    total -= d.id * self.trips[d][otrip]
            self.mdl.add_constraint(ct=total == 0)
        print("Set incoming driver is the same as outgoing driver constraints")

        """
        Capacity Constraints
        """
        # for d in drivers:
        #     for loc in requestNodes:
        #         for otrip in filtered(d, outtrips[loc]):
        #             for intrip in filtered(d, intrips[loc]):
        #                 mdl.add_if_then(trips[d][intrip] + trips[d][otrip] == 2, then_ct= nodeCaps[loc] == caps[d][otrip] - caps[d][intrip]) # !!!! MAJOR FIX
        for loc in self.requestNodes:
            incaps = 0
            ocaps = 0
            tripsum = 0
            for d in self.drivers:
                for otrip in self.filtered(d, self.outtrips[loc]):
                    ocaps += self.caps[d][otrip]
                for intrip in self.filtered(d, self.intrips[loc]):
                    incaps += self.caps[d][intrip]
            self.mdl.add_constraint(ocaps == incaps + self.nodeCaps[loc])
        print("Set capacity value constraints")

        for d in self.drivers:
            for loc in self.driverStart:
                for otrip in self.filtered(d, self.outtrips[loc]):
                    self.mdl.add_constraint(ct=self.caps[d][otrip] == 0)
            for loc in self.driverEnd:
                for intrip in self.filtered(d, self.intrips[loc]):
                    self.mdl.add_constraint(ct=self.caps[d][intrip] == 0)
        print("Set initial and final trip capacity constraints")

    def __prepare_objective(self):
        """
        Objective function
        """
        obj = 0
        for d, driver_trips in self.trips.items():
            for t, var in driver_trips.items():
                obj += t.lp.miles * var
        print("Defined Objective Function")
        self.mdl.minimize(obj)

    def solve(self, solution_file):
        try:
            if self.STAGE1_TIME and self.STAGE2_TIME:
                if self.STAGE1_GAP:
                    pL = GapListener(self.STAGE1_TIME, self.STAGE1_GAP)
                else:
                    pL = TimeListener(self.STAGE1_TIME)
                self.mdl.add_progress_listener(pL)
                first_solve = self.mdl.solve()
                print("First solve status: " + str(self.mdl.get_solve_status()))
                print("First solve obj value: " + str(self.mdl.objective_value))
                print("Relaxing single rider requirements constraints")
                self.mdl.remove_constraints(self.constraintsToRem)
                print("Warm starting from single rider constrained solution")
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
            elif self.TIME_LIMIT:
                if self.MIP_GAP:
                    pL = GapListener(self.TIME_LIMIT, self.MIP_GAP)
                else:
                    pL = TimeListener(self.TIME_LIMIT)
                self.mdl.add_progress_listener(pL)
                self.mdl.solve()
                print("Final solve status: " + str(self.mdl.get_solve_status()))
                print("Final Obj value: " + str(self.mdl.objective_value))
            else:
                print("Must specify individual 2 stage time limits or a single time limit parameter")
                exit(1)
        except DOcplexException as e:
            print(e)
        finally:
            driverMiles = dict()
            for d, driver_trips in self.trips.items():
                driverMiles[d] = 0
                for t, var in driver_trips.items():
                    if self.caps[d][t].solution_value >= 0.1:
                        driverMiles[d] += t.lp.miles

            def tripGen():
                for d, driver_trips in self.trips.items():
                    for t, var in driver_trips.items():
                        if t.lp.o not in self.requestStart or var.solution_value != 1:
                            continue
                        yield (d, t)
            with open(solution_file, 'w') as output:
                output.write(
                    'trip_id, driver_id,driver_name ,trip_pickup_address, trip_pickup_time, est_pickup_time, trip_dropoff_adress, trip_dropoff_time, est_dropoff_time, trip_los, est_miles, est_time\n')
                for d, t in sorted(tripGen(), key=lambda x: self.times[x[0]][x[1]].solution_value):
                    end_time = -1
                    rE = self.requestPair[t.lp.o]
                    for intrip in self.filtered(d, self.intrips[rE]):
                        if self.trips[d][intrip].solution_value == 1:
                            end_time = self.times[d][intrip].solution_value + intrip.lp.time
                            break
                    if end_time < 0:
                        print("Something wrong")
                    required_end = self.all_trips[self.primaryTID[t.lp.o]].end
                    ptrip = self.all_trips[self.primaryTID[t.lp.o]]
                    output.write(str(self.primaryTID[t.lp.o]) + "," + str(d.id) + "," + str(d.name) + ",\"" + str(
                        t.lp.o[:4]) + "\"," + str(t.start) + "," + str(self.times[d][t].solution_value) + ",\"" +
                                 str(t.lp.d[:4]) + "\"," + str(rE) + "," + str(required_end) + "," + str(
                        end_time) + "," +
                                 str(t.los) + "," + str(ptrip.lp.miles) + "," + str(ptrip.lp.time) + "\n")
            print("Total Number of primary trip miles by each driver: ")
            print(driverMiles)
