import random
from copy import copy
from datetime import timedelta
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from docloud.status import JobSolveStatus
from docplex.mp.conflict_refiner import ConflictRefiner, VarLbConstraintWrapper, VarUbConstraintWrapper
from docplex.mp.model import Model
from docplex.mp.relaxer import Relaxer
from docplex.mp.utils import DOcplexException
from plotly.subplots import make_subplots

from lib.Trip import Trip, locations, InvalidTripException, TripType, Location
from lib.constants import FIFTEEN
from lib.listeners import TimeListener, GapListener

class GeneralOptimizer:
    def filtered(self, d, iter):
        return filter(lambda t: not ((t.lp.o in self.driverNodes and t.lp.o[:4] != d.address[:4]) or (
                    t.lp.d in self.driverNodes and t.lp.d[:4] != d.address[:4]))
                                and t.los in d.los
                                # and
                                and not (abs(self.nodeCaps[t.lp.o] + self.nodeCaps[t.lp.d]) > d.capacity), iter)


    def __init__(self, trips, drivers, params, name = None):
        self.drivers_inp = drivers
        self.trips_inp = trips
        if not name:
            self.mdl = Model(name=params["MODEL_NAME"])
        else:
            self.mdl = Model(name=name)

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
        self.nodeOpen = dict()  # Earliest departure time from a node
        self.nodeClose = dict()  # earliest arrival time to a node
        self.primaryTID = dict()  # Map from starting location to ID of primary trip from that location
        self.merges = dict()  # Map from merge trip to incoming primary trip
        self.revenues = dict() # Map from start node to revenue of the trip
        self.badPairs = dict() # Map from Pickup location of trip pair to dropoff of incoming trip pair
        # Decision Variable Structures
        self.trips = dict()  # Map from driver to map of trip to model variable
        self.times = dict()  # Map from driver to map of trip to model variable
        self.caps = dict()  # Map from driver to map of trip to model variable
        self.revs = dict() # Map from driver to revenue variable

        # Additional Structures
        self.intrips = dict()  # Map from driver to Map from location to list of trips
        self.outtrips = dict()  # Map from driver to Map from location to list of trips

        # Constants
        self.TRIPS_TO_DO = params["TRIPS_TO_DO"]
        self.NUM_DRIVERS = params["NUM_DRIVERS"]
        self.EARLY_PICK_WINDOW = params["EARLY_PICKUP_WINDOW"]
        self.EARLY_DROP_WINDOW = params["EARLY_DROP_WINDOW"]
        self.LATE_PICK_WINDOW = params["LATE_PICKUP_WINDOW"]
        self.LATE_DROP_WINDOW = params["LATE_DROP_WINDOW"]
        self.CAP = params["DRIVER_CAP"]
        self.ROUTE_LIMIT = params["ROUTE_LIMIT"]
        self.ROUTE_LIMIT_PEN = params["ROUTE_LIMIT_PENALTY"]
        self.EARLY_DAY_TIME = params["EARLY_DAY_TIME"]
        self.MERGE_PEN = params["MERGE_PENALTY"]
        self.REVENUE_PEN = params["REVENUE_PENALTY"]

        self.STAGE1_TIME = params["STAGE1_TIME"]
        self.STAGE1_GAP = params["STAGE1_GAP"]
        self.STAGE2_TIME = params["STAGE2_TIME"]
        self.STAGE2_GAP = params["STAGE2_GAP"]

        # Prepare Model
        self.obj = 0.0
        self.constraintsToRem = set()
        self.ed_constr = set()
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
            rev = trip.rev
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
            self.nodeClose[start] = pick + self.LATE_PICK_WINDOW  # 0
            self.nodeOpen[start] = pick - self.EARLY_PICK_WINDOW  # max(0, pick - BUFFER)
            self.nodeClose[end] = drop + self.LATE_DROP_WINDOW
            self.nodeOpen[end] = pick - self.EARLY_PICK_WINDOW + trip.lp.time  # 0 # max(0, pick - BUFFER) + t.lp.time
            self.all_trips[id] = trip
            self.primary_trips[(start, end)] = trip
            self.primaryTID[start] = trip.id
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
            if trip.type == TripType.MERGE:
                if 'B' in trip.id:
                    self.merges[trip] = self.all_trips[trip.id[:-1] + 'A']
                elif 'C' in trip.id:
                    self.merges[trip] = self.all_trips[trip.id[:-1] + 'B']
                else:
                    print("Unexpected Trip ID", trip.id)
                    exit(1)
            if 'B' in trip.id:
                prevtrip = self.all_trips[trip.id[:-1] + 'A']
                self.badPairs[prevtrip.lp.o] = end
                self.badPairs[start] = prevtrip.lp.d
            elif 'C' in trip.id:
                prevtrip = self.all_trips[trip.id[:-1] + 'B']
                self.badPairs[prevtrip.lp.o] = end
                self.badPairs[start] = prevtrip.lp.d
            if count == self.TRIPS_TO_DO:
                break
        print("Number of Trips:", count)

    def __prepare_driver_parameters(self):
        count = 0
        for driver in self.drivers_inp:
            d = copy(driver)
            self.drivers.append(d)
            d.capacity = self.CAP
            start = d.address
            end = d.address
            self.driverNodes.add(start)
            self.driverNodes.add(end)
            self.driverStart.add(start)
            self.driverEnd.add(end)
            self.nodeCaps[start] = 0
            self.nodeCaps[end] = 0
            self.revenues[start] = 0
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
                t = Trip(dS, rS, 0, id, None, 0.0, 1.0, 0.0, prefix=False, suffix=True)
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
                t = Trip(rE, dE, 0, id, None, 0.0, 1.0, 0.0, prefix=False, suffix=True)
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
                        rE in self.requestPair and self.requestPair[rE] == rS) or (rS in self.badPairs and self.badPairs[rS] == rE):
                    continue
                try:
                    t = Trip(rS, rE, 0, id, None, self.nodeOpen[rS], self.nodeClose[rE], 0.0, prefix=False, suffix=True)
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
                t.write(pair[0]+ "," + pair[1] + "," + str(trp.lp.time) + "\n")
                c.write(pair[0]+ "," + pair[1] + "," + str(trp.lp.miles) + "\n")


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
                if dS[:-4] != d.address[:-4]:
                    continue
                total = 0
                for otrip in self.filtered(d, self.outtrips[dS]):
                    total -= self.trips[d][otrip]
                self.mdl.add_constraint(ct=total == -1, ctname='driverout' + '_' + str(d.id))
        for d in self.drivers:
            for dE in self.driverEnd:
                if dE[:-4] != d.address[:-4]:
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
        # for loc in self.requestNodes:
        #     intripSum = 0
        #     intripTimes = 0
        #     intripStarts = self.nodeDeps[loc]
        #     intripEnds = self.nodeArrs[loc]
        #     for d in self.drivers:
        #         for intrip in self.filtered(d, self.intrips[loc]):
        #             intripSum += self.times[d][intrip]
        #             intripTimes += intrip.lp.time * self.trips[d][intrip]
        #             # intripEnds += intrip.end * trips[d][intrip]
        #     self.mdl.add_constraint(intripSum + intripTimes <= intripEnds)
        #     # obj += dropOffPenalty * ((intripSum + intripTimes) - intripEnds)
        for loc in self.requestEnd:
            intripSum = 0
            intripTimes = 0
            intripStarts = self.nodeOpen[loc]
            intripEnds = self.nodeClose[loc]
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
        # for loc in self.requestNodes:
        #     otripSum = 0
        #     otripStarts = self.nodeArrs[loc]
        #     otripEnds = self.nodeDeps[loc]
        #     for d in self.drivers:
        #         for otrip in self.filtered(d, self.outtrips[loc]):
        #             otripSum += self.times[d][otrip]
        #             # otripStarts += otrip.start * trips[d][otrip]
        #         # obj += pickupEarlyPenalty * (otripStarts - (otripSum + BUFFER))
        #         # obj += pickupLatePenalty * (otripStarts - (otripSum - BUFFER))
        #     # self.mdl.add_constraint(otripSum + self.PICK_WINDOW >= otripStarts)
        #     # self.mdl.add_constraint(otripSum <= otripStarts + self.PICK_WINDOW)
        #     self.mdl.add_constraint(otripSum >= otripStarts)
        #     self.mdl.add_constraint(otripSum <= otripEnds)

        for loc in self.requestStart:
            otripSum = 0
            otripEnds = self.nodeClose[loc]
            otripStarts = self.nodeOpen[loc]
            for d in self.drivers:
                for otrip in self.filtered(d, self.outtrips[loc]):
                    otripSum += self.times[d][otrip]
                    # otripStarts += otrip.start * trips[d][otrip]
                # obj += pickupEarlyPenalty * (otripStarts - (otripSum + BUFFER))
                # obj += pickupLatePenalty * (otripStarts - (otripSum - BUFFER))
            # self.mdl.add_constraint(otripSum + self.PICK_WINDOW >= otripStarts)
            # self.mdl.add_constraint(otripSum <= otripStarts + self.PICK_WINDOW)
            self.mdl.add_constraint(otripSum >= otripStarts)
            self.mdl.add_constraint(otripSum <= otripEnds)
        print("Set departure time constraints")

        """
        Precedence Constraints
        """
        for trp in self.all_trips:
            if isinstance(trp, str):
                if (trp.endswith('A') and (trp[:-1] + 'B' in self.all_trips)) or (trp.endswith('B') and (trp[:-1] + 'C' in self.all_trips)):
                    main_trip = self.all_trips[trp]
                    main_tripo = main_trip.lp.o
                    main_tripd = main_trip.lp.d
                    isum = 0
                    itimeSum = 0
                    for d in self.drivers:
                        for intrip in self.filtered(d, self.intrips[main_tripo]):
                            isum += self.times[d][intrip]
                            itimeSum += intrip.lp.time * self.trips[d][intrip]
                    isum2 = 0
                    itimeSum2 = 0
                    for d2 in self.drivers:
                        for intrip in self.filtered(d2, self.intrips[main_tripd]):
                            isum2 += self.times[d2][intrip]
                            itimeSum2 += intrip.lp.time * self.trips[d2][intrip]

                    self.mdl.add_constraint(isum + itimeSum + main_trip.lp.time <= isum2 + itimeSum2)

                    main_trip_loc = self.all_trips[trp].lp.d
                    alt_trip_loc = None
                    if trp.endswith('A'):
                        alt_trip_loc = self.all_trips[trp[:-1] + "B"].lp.o
                    elif trp.endswith('B'):
                        alt_trip_loc = self.all_trips[trp[:-1] + "C"].lp.o
                    else:
                        print('Invalid trip id ', trp)
                        exit(1)
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
        self.__prepare_custom_constraints()

    def __prepare_custom_constraints(self):
        print("Adding Custom Defined Constraints")

        """
        Route Length Penalty
        """
        for d in self.drivers:
            otime = 0
            itime = 0
            for dS in self.driverStart:
                if dS[:-4] != d.address[:-4]:
                    continue
                for otrip in self.filtered(d, self.outtrips[dS]):
                    otime += self.times[d][otrip]
                break
            for dE in self.driverEnd:
                if dE[:-4] != d.address[:-4]:
                    continue
                for intrip in self.filtered(d, self.intrips[dE]):
                    itime += self.times[d][intrip]
                break
            # self.mdl.add_constraint(ct= itime - otime <= self.ROUTE_LIMIT , ctname='Route limit' + '_' + str(d.id))
            self.obj += self.ROUTE_LIMIT_PEN * (itime - otime)
            if not d.ed:
                try:
                    c = self.mdl.add_constraint(otime >= self.EARLY_DAY_TIME)
                    self.ed_constr.add(c)
                except DOcplexException as e:
                    if 'trivially' not in e.message:
                        raise e
                    print(itime, otime)
                    print("Can't restrict early day for", d.name)

        """
        Merge Trip Requirements
        """
        for d in self.drivers:
            for mer in self.filtered(d, self.merges):
                self.mdl.add_constraint(ct = self.trips[d][mer] == self.trips[d][self.merges[mer]])
                self.obj += self.MERGE_PEN * (self.times[d][mer] - (self.times[d][self.merges[mer]] + self.merges[mer].lp.time * self.trips[d][mer])) * (24)
                # self.obj += self.MERGE_PEN * (self.trips[d][mer] - self.trips[d][self.merges[mer]])
        """
        Equalizing Revenue Penalty
        """
        self.rev_max = self.mdl.continuous_var(0)
        self.rev_min = self.mdl.continuous_var(0)
        for d in self.drivers:
            self.revs[d] = self.mdl.continuous_var(lb=0, name="Revenue" + str(d.id))
            self.mdl.add_constraint(self.revs[d] == sum(self.revenues[t.lp.o] * self.trips[d][t] for t in self.filtered(d, self.all_trips.values())))
            self.mdl.add_constraint(self.rev_max >= self.revs[d])
            self.mdl.add_constraint(self.rev_min <= self.revs[d])
        self.obj += self.REVENUE_PEN * (self.rev_max - self.rev_min)

    def __prepare_objective(self):
        """
        Objective function
        """
        for d, driver_trips in self.trips.items():
            for t, var in driver_trips.items():
                # obj += t.lp.miles * var
                self.obj += 1440 * t.lp.time * var
        print("Defined Objective Function")
        self.mdl.minimize(self.obj)

    def solve(self, solution_file):
        try:
            if self.STAGE1_TIME and self.STAGE2_TIME:
                if self.STAGE1_GAP:
                    pL = GapListener(self.STAGE1_TIME, self.STAGE1_GAP)
                else:
                    pL = TimeListener(self.STAGE1_TIME)
                self.mdl.add_progress_listener(pL)
                first_solve = self.mdl.solve()
                if first_solve and (first_solve.solve_status == JobSolveStatus.FEASIBLE_SOLUTION or first_solve.solve_status == JobSolveStatus.OPTIMAL_SOLUTION):
                    print("First solve status: " + str(self.mdl.get_solve_status()))
                    print("First solve obj value: " + str(self.mdl.objective_value))
                    driverMiles = self.__write_sol(solution_file+'stage1')
                    print("Total Number of trip miles by each driver after stage 1: ")
                    print(driverMiles)
                    self.visualize(solution_file+'stage1', 'stage1vis.html')
                else:
                    print("Stage 1 Infeasible with ED")
                if not first_solve or first_solve.solve_status == JobSolveStatus.INFEASIBLE_SOLUTION:
                    print("Relaxing Early Day Constraints")
                    self.mdl.remove_constraints(self.ed_constr)
                print("Relaxing single rider requirements constraints")
                self.mdl.remove_constraints(self.constraintsToRem)
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
            driverMiles = self.__write_sol(solution_file)
            print("Total Number of trip miles by each driver: ")
            print(driverMiles)

    def visualize(self, sfile, vfile='visualized.html', open_after=False):
        def names(id):
            return "Driver " + str(id) + " Route"
        def get_labels(trips, addr):
            data = "<br>".join(
               "0" * (10 - len(str(t['trip_id']))) + str(t['trip_id']) + "  |  " + str(timedelta(days=float(t['est_pickup_time']))).split('.')[0] +
                "  |  " + str(t['driver_id']) for t in trips
            )
            return addr + "<br><b>TripID,             Time,      DriverID </b><br>" + data

        sol_df = pd.read_csv(sfile)
        driver_ids = list(d.id for d in self.drivers)
        titles = [names(i) for i in driver_ids]
        titles.insert(0, "Map")
        titles.insert(1, "Driver Summary: " + self.mdl.name)
        subplots = [[{"type": "table"}]] * (len(self.drivers) + 1)
        subplots.insert(0, [{"type": "scattermapbox"}])
        map_height = 600 / (600 + 2000 + 400 * (len(self.drivers)))
        summary_height = 600 / (600 + 2000 + 400 * (len(self.drivers)))
        heights = [(1 - map_height - summary_height - 0.12) / ((len(self.drivers)))] * (len(self.drivers))
        heights.insert(0, map_height)
        heights.insert(1, summary_height)
        fig = make_subplots(
            rows=2 + len(self.drivers), cols=1,
            vertical_spacing=0.015,
            subplot_titles=titles,
            specs=subplots,
            row_heights=heights
        )
        all_x = []
        all_y = []
        locations = dict()
        addresses = dict()
        for i, d in enumerate(self.drivers):
            r = lambda: random.randint(0, 255)
            col = '#%02X%02X%02X' % (r(), r(), r())
            filtered_trips = sol_df[sol_df['driver_id']==d.id]
            points, trips = self.__get_driver_coords(filtered_trips, d)
            x, y = zip(*points)
            details = [[str(t['trip_id']) for _, t in filtered_trips.iterrows()],
                       [t['trip_pickup_address'] for _,t in filtered_trips.iterrows()],
                       [t['trip_dropoff_address'] for _,t in filtered_trips.iterrows()],
                       [str(timedelta(days=float(t['est_pickup_time']))).split('.')[0] for _,t in filtered_trips.iterrows()],
                       [str(timedelta(days=float(t['trip_pickup_time']))).split('.')[0] for _,t in filtered_trips.iterrows()],
                       [str(timedelta(days=float(t['est_dropoff_time']))).split('.')[0] for _,t in filtered_trips.iterrows()],
                       [str(timedelta(days=float(t['trip_dropoff_time']))).split('.')[0] for _,t in filtered_trips.iterrows()],
                       [str(t['est_miles']) for _,t in filtered_trips.iterrows()],
                       [str(t['trip_los']) for _,t in filtered_trips.iterrows()],
                       [str(t['trip_rev']) for _,t in filtered_trips.iterrows()],
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
                name=names(d.id),

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
                    locations[point] = list(sorted(locations[point], key=lambda x: float(x['est_pickup_time'])))
                else:
                    locations[point] = [trips[idx]]
                if point not in addresses:
                    addresses[point] = trips[idx]['trip_pickup_address']

        lon, lat = map(list, zip(*locations.keys()))
        labels = [get_labels(locations[k], addresses[k]) for k in locations.keys()]
        for d in self.drivers:
            lon.append(Location(d.address[:-4]).coord[1])
            lat.append(Location(d.address[:-4]).coord[0])
            labels.append(d.address[:-4] + "<br>Driver " + str(d.id) + " Home")
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
        names, ids, times, ep, ld,  miles, rev = zip(*(self.__get_driver_trips_times_miles_rev(sol_df, id) for id in driver_ids))
        names = list(names)
        ids = list(ids)
        times = list(times)
        ep = list(ep)
        ld = list(ld)
        miles = list(miles)
        rev = list(rev)
        ids.append("Average")
        times.append(sum(times)/len(times))
        ep.append(sum(ep)/len(ep))
        ld.append(sum(ld)/len(ld))
        miles.append(sum(miles)/len(miles))
        rev.append(sum(rev)/len(rev))
        times = list(map(lambda t: str(timedelta(days=t)).split('.')[0],times))
        ep = list(map(lambda t: str(timedelta(days=t)).split('.')[0],ep))
        ld = list(map(lambda t: str(timedelta(days=t)).split('.')[0],ld))
        miles = list(map(str, miles))
        rev = list(map(str, rev))
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Driver", "Trips", "Time", "Earliest Pickup", "Latest Dropoff", "Miles", "Revenue"],
                    font=dict(size=10),
                    align="left"
                ),
                cells=dict(
                    values=[names, ids, times, ep, ld, miles, rev],
                    align="left")
            ),
            row=2, col=1,
        )
        fig.update_mapboxes(zoom=10,center=go.layout.mapbox.Center(
                lat=np.mean(all_y),
                lon=np.mean(all_x)),
         style='open-street-map')

        fig.update_layout(
            title_text=self.mdl.name,
            showlegend=True,
            height=(600 + 400 * (len(self.drivers) + 1))
        )
        fig.write_html(vfile, auto_open=open_after)

    def __get_driver_coords(self, filtered_trips, driver):
        pairs = []
        pairs.append((0.0, Location(driver.address[:-4]).rev_coord(), {}))
        for idx, t in filtered_trips.iterrows():
            pairs.append((float(t['est_pickup_time']), Location(t['trip_pickup_address']).rev_coord(), t))
            pairs.append((float(t['est_dropoff_time']), Location(t['trip_dropoff_address']).rev_coord(), {'est_pickup_time': t['est_dropoff_time'], 'driver_id': driver.id, 'trip_id': 'INTER', 'trip_pickup_address': t['trip_dropoff_address']}))

        pairs.append((1.0, Location(driver.address[:-4]).rev_coord(), {}))
        _, coords, trips = zip(*sorted(pairs, key=lambda x: x[0]))
        return coords, trips

    def __get_driver_trips_times_miles_rev(self, sol_df, id):
        filtered_trips = sol_df[sol_df['driver_id'] == id]
        try:
            ep = (min(float(t['est_pickup_time']) for _, t in filtered_trips.iterrows()))
        except ValueError:
            ep = '0'
        try:
            ld = (max(float(t['est_dropoff_time']) for _, t in filtered_trips.iterrows()))
        except:
            ld = '0'
        name = ("".join(str(t['driver_name']) for _, t in filtered_trips.sample(1).iterrows())) + ";" + str(id)
        trps = ", ".join(t['trip_id'] for _, t in filtered_trips.iterrows())
        time = (sum(float(t['est_time']) for _, t in filtered_trips.iterrows()))
        m = (sum(float(t['est_miles']) for _, t in filtered_trips.iterrows()))
        r = (sum(float(t['trip_rev']) for _, t in filtered_trips.iterrows()))
        return name, trps, time, ep, ld, m, r

    def __write_sol(self, solution_file):
        driverMiles = dict()
        for d, driver_trips in self.trips.items():
            driverMiles[d] = 0
            for t, var in driver_trips.items():
                if self.trips[d][t].solution_value >= 0.1:
                    driverMiles[d] += t.lp.miles

        def tripGen():
            for d, driver_trips in self.trips.items():
                for t, var in driver_trips.items():
                    if t.lp.o not in self.requestStart or var.solution_value != 1:
                        continue
                    yield (d, t)
        # def tripGen_debug(d):
        #     for t, var in self.trips[d].items():
        #         if var.solution_value != 1:
        #             continue
        #         yield (d, t)
        # for dr in self.drivers:
        #     for d, t in sorted(tripGen_debug(dr), key=lambda x: self.times[x[0]][x[1]].solution_value):
        #         print(d.name, t.lp.o, t.lp.d, self.times[d][t].solution_value, t.lp.time)

        with open(solution_file, 'w') as output:
            output.write(
                'trip_id,driver_id,driver_name,trip_pickup_address,trip_pickup_time,est_pickup_time,trip_dropoff_address,trip_dropoff_time,est_dropoff_time,trip_los,est_miles,est_time,trip_rev\n')
            count = 0
            for d, t in sorted(tripGen(), key=lambda x: self.times[x[0]][x[1]].solution_value):
                count += 1
                end_time = -1
                rE = self.requestPair[t.lp.o]
                for intrip in self.filtered(d, self.intrips[rE]):
                    if self.trips[d][intrip].solution_value == 1:
                        end_time = self.times[d][intrip].solution_value + intrip.lp.time
                        if end_time < self.times[d][t].solution_value:
                            print('Something wrong')
                            print(sum(self.trips[d][intrip].solution_value for intrip in self.filtered(d, self.intrips[rE])))
                            print(rE)
                            print(t.lp.o, t.lp.d)
                            print(intrip.lp.o, intrip.lp.d)
                            print(t.id, self.times[d][t].solution_value, self.times[d][intrip].solution_value, intrip.lp.time)
                        break
                if end_time < 0:
                    print("Something wrong")
                required_end = self.all_trips[self.primaryTID[t.lp.o]].end
                ptrip = self.all_trips[self.primaryTID[t.lp.o]]
                output.write(str(self.primaryTID[t.lp.o]) + "," + str(d.id) + "," + str(d.name) + ",\"" + str(
                    t.lp.o[:-4]) + "\"," + str(t.start) + "," + str(self.times[d][t].solution_value) + ",\"" +
                             str(rE[:-4]) + "\"," + str(required_end) + "," + str(end_time) + "," +
                             str(t.los) + "," + str(ptrip.lp.miles) + "," + str(ptrip.lp.time) + "," + str(
                    self.revenues[t.lp.o]) + "\n")
        return driverMiles
