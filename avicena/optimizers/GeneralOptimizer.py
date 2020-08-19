from copy import copy
from typing import List, Any, Dict, Iterable
import logging
import pandas as pd
from docloud.status import JobSolveStatus
from docplex.mp.utils import DOcplexException
from pandas import DataFrame

from avicena.models.Trip import Trip, Location
from avicena.models.Driver import Driver
from avicena.optimizers.BaseOptimizer import BaseOptimizer
from avicena.optimizers.solver_util.cplex.Listeners import GapListener, TimeListener
from avicena.util.Exceptions import InvalidTripException, SolutionNotFoundException, DuplicateAddressException
from avicena.util.Geolocator import find_coord_lat_lon
from avicena.util.ParserUtil import convert_time
from avicena.util.TimeWindows import get_time_window_by_hours_minutes


log = logging.getLogger(__name__)


class GeneralOptimizer(BaseOptimizer):
    """
    The GeneralOptimizer uses CPLEX to solve the Patient Dispatch problem.
    The exact formulation can be found at: <will upload later>
    """

    def __init__(self, trips: List[Trip], drivers: List[Driver], name: str, date: str, speed: int,
                 config: Dict[str, Any]) -> None:
        """
        Initialize a General Optimizer
        :param trips: List of valid Trip objects that were parsed and cleaned from the input file
        :param drivers: List of drivers selected to be dispatched for this model
        :param name: Name of the given model
        :param date: Date for which the model is running
        :param speed: Assumed travelling speed
        :param config: Configuration Details for this optimizer type and its parameters
        """
        super().__init__(trips, drivers, name, date, speed, config)
        self.drivers = list()  # List of all Drivers
        self.primary_trips = dict()  # Map Primary trip pair to trip object
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
        self.revenues = dict()  # Map from start node to revenue of the trip
        self.wheelchair_locations = set()  # Set of locations where wheelchair trips start

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
        self.TRIPS_TO_DO = config["max_trips"]
        self.NUM_DRIVERS = config["max_drivers"]
        self.EARLY_PICK_WINDOW = get_time_window_by_hours_minutes(0, config["early_pickup_window"])
        self.EARLY_DROP_WINDOW = get_time_window_by_hours_minutes(0, config["late_pickup_window"])
        self.LATE_PICK_WINDOW = get_time_window_by_hours_minutes(0, config["early_drop_window"])
        self.LATE_DROP_WINDOW = get_time_window_by_hours_minutes(0, config["late_drop_window"])
        self.CAP = config["driver_capacity"]
        self.ROUTE_LIMIT = get_time_window_by_hours_minutes(0, config["route_limit"])
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
        self.solution_df = None
        self.single_rider_constraints = set()
        self.early_day_constraints = set()
        self.__prepare_trip_parameters()
        self.__prepare_driver_parameters()
        self.__generate_variables()
        self.__prepare_constraints()
        self.__prepare_objective()

    def filter_driver_feasible_trips(self, driver: Driver, iter: Iterable[Trip]) -> Iterable[Trip]:
        """
        Using an iterable of trips, return a filter of trips that is allowed for the driver. This optimizes the number
        of constraints and variables generated.
        :param driver: Driver object
        :param iter: Iterable of Trips
        :return: Filter generator of feasible trips that a given driver can perform
        """
        return filter(lambda t: not (
                    (t.lp.o in self.driver_nodes and t.lp.o.get_clean_address() != driver.get_clean_address()) or (
                    t.lp.d in self.driver_nodes and t.lp.d.get_clean_address() != driver.get_clean_address()))
                                and t.required_level_of_service in driver.level_of_service
                                and not (
                    abs(self.node_capacities[t.lp.o] + self.node_capacities[t.lp.d]) > driver.capacity), iter)

    def __prepare_trip_parameters(self) -> None:
        """
        Populate data structures with trip associated parameters such as mappings between pickups and dropoffs of trips,
        opening and closing windows of locations, revenue for trips, etc.
        """
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
                raise DuplicateAddressException(f"Duplicate pickup address string {start} for trip ID {id} found in node set. "
                                                "All address strings for must be unique across all trip pickups and dropoffs. "
                                                "Consider adding a suffix to the address or increasing the length of the suffix "
                                                "if you frequently encounter this problem.")
            b = len(self.request_nodes)
            self.request_nodes.add(end)
            if b == len(self.request_nodes):
                raise DuplicateAddressException(f"Duplicate dropoff address string {end} for trip ID {id} found in node set. "
                                                "All address strings for must be unique across all trip pickups and dropoffs. "
                                                "Consider adding a suffix to the addresses or increasing the length of the suffix "
                                                "if you frequently encounter this problem.")
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
                    raise InvalidTripException(f"Unexepected trip id {trip.id} with merge flag set to True. Only B or C Legs can be merge trips.")
            if count == self.TRIPS_TO_DO:
                break
        log.info(f"Number of Trips: {count}")

    def __prepare_driver_parameters(self) -> None:
        """
        Prepare data structures that store driver specific details such as driver nodes, and capacities.
        """
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
        log.info(f"Number of Drivers: {count}")

    def __generate_variables(self) -> None:
        """
        Generate the model variables
        """
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
                    t = Trip(rS, rE, space, id, self.node_window_open[rS], self.node_window_close[rE], self.SPEED,
                             False, 0.0)
                except InvalidTripException:
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
                self.capacity_vars[d][t] = self.mdl.continuous_var(lb=0, ub=d.capacity,
                                                                   name='q' + '_' + str(d.id) + '_' + str(t.id))
                self.mdl.add_constraint(self.capacity_vars[d][t] - self.trip_vars[d][t] * d.capacity <= 0)

    def __prepare_constraints(self) -> None:
        """
        Generate the model constraints.
        """

        """
        Request Requirements
        """
        for trp in self.all_trips:
            if isinstance(trp, str):
                driver_id_sum = 0
                for d in self.drivers:
                    if self.all_trips[trp].required_level_of_service in d.level_of_service:
                        driver_id_sum += self.trip_vars[d][self.all_trips[trp]]
                con = self.mdl.add_constraint(ct=driver_id_sum == 1)
                self.single_rider_constraints.add(con)

        """
        Flow Conservation
        """
        for rN in self.request_nodes:
            total_flow_in = 0
            total_flow_out = 0
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[rN]):
                    total_flow_in += self.trip_vars[d][intrip]
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[rN]):
                    total_flow_out -= self.trip_vars[d][otrip]
            self.mdl.add_constraint(ct=total_flow_in <= 1, ctname='flowin' + '_' + str(rN)[:5])
            self.mdl.add_constraint(ct=total_flow_out >= -1, ctname='flowout' + '_' + str(rN)[:5])
            self.mdl.add_constraint(ct=total_flow_in + total_flow_out == 0, ctname='flowinout' + '_' + str(rN)[:5])
        for d in self.drivers:
            for dS in self.driver_starts:
                if dS.get_clean_address() != d.get_clean_address():
                    continue
                driver_id_sum = 0
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[dS]):
                    driver_id_sum -= self.trip_vars[d][otrip]
                self.mdl.add_constraint(ct=driver_id_sum == -1, ctname='driverout' + '_' + str(d.id))
        for d in self.drivers:
            for dE in self.driver_ends:
                if dE.get_clean_address() != d.get_clean_address():
                    continue
                driver_id_sum = 0
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[dE]):
                    driver_id_sum += self.trip_vars[d][intrip]
                self.mdl.add_constraint(ct=driver_id_sum == 1, ctname='driverin' + '_' + str(d.id))

        log.info("Set flow conservation constraints")

        """
        Time Constraints
        """
        for loc in self.request_ends:
            intrip_time_var_sum = 0
            intrip_travel_time_sum = 0
            location_close_window = self.node_window_close[loc]
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    intrip_time_var_sum += self.time_vars[d][intrip]
                    intrip_travel_time_sum += intrip.lp.time * self.trip_vars[d][intrip]
            self.mdl.add_constraint(intrip_time_var_sum + intrip_travel_time_sum <= location_close_window)
        log.info("Set arrival time constriants")

        for loc in self.request_starts:
            outtrip_time_var_sum = 0
            location_close_window = self.node_window_close[loc]
            location_open_window = self.node_window_open[loc]
            for d in self.drivers:
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    outtrip_time_var_sum += self.time_vars[d][otrip]
            self.mdl.add_constraint(outtrip_time_var_sum >= location_open_window)
            self.mdl.add_constraint(outtrip_time_var_sum <= location_close_window)
        log.info("Set departure time constraints")

        """
        Precedence Constraints
        """
        for trp in self.all_trips:
            if isinstance(trp, str):
                if (trp.endswith('A') and (trp[:-1] + 'B' in self.all_trips)) or (
                        trp.endswith('B') and (trp[:-1] + 'C' in self.all_trips)):
                    main_origin = self.all_trips[trp].lp.o
                    main_dest = self.all_trips[trp].lp.d
                    if trp.endswith('A'):
                        alt_origin = self.all_trips[trp[:-1] + "B"].lp.o
                        alt_dest = self.all_trips[trp[:-1] + "B"].lp.d
                    else:
                        alt_origin = self.all_trips[trp[:-1] + "C"].lp.o
                        alt_dest = self.all_trips[trp[:-1] + "C"].lp.d

                    main_origin_outtrip_time_var_sum = 0
                    for d in self.drivers:
                        for itrip in self.filter_driver_feasible_trips(d, self.outtrips[main_origin]):
                            main_origin_outtrip_time_var_sum += self.time_vars[d][itrip]
                    main_dest_intrip_time_var_sum = 0
                    main_dest_incoming_travel_time_sum = 0
                    for d in self.drivers:
                        for itrip in self.filter_driver_feasible_trips(d, self.intrips[main_dest]):
                            main_dest_intrip_time_var_sum += self.time_vars[d][itrip]
                            main_dest_incoming_travel_time_sum += itrip.lp.time * self.trip_vars[d][itrip]
                    alt_origin_outgoing_time_var_sum = 0
                    for d2 in self.drivers:
                        for otrip in self.filter_driver_feasible_trips(d2, self.outtrips[alt_origin]):
                            alt_origin_outgoing_time_var_sum += self.time_vars[d2][otrip]
                    alt_dest_incoming_time_var_sum = 0
                    for d2 in self.drivers:
                        for otrip in self.filter_driver_feasible_trips(d2, self.outtrips[alt_dest]):
                            alt_dest_incoming_time_var_sum += self.time_vars[d2][otrip]
                    self.mdl.add_constraint(main_origin_outtrip_time_var_sum <= main_dest_intrip_time_var_sum)
                    self.mdl.add_constraint(
                        main_dest_intrip_time_var_sum + main_dest_incoming_travel_time_sum <= alt_origin_outgoing_time_var_sum)
                    self.mdl.add_constraint(alt_origin_outgoing_time_var_sum <= alt_dest_incoming_time_var_sum)
        log.info("Set primary trip precedence constraints")

        for loc in self.request_nodes:
            incoming_time_var_sum, outgoing_time_var_sum = 0, 0
            travel_time_sum = 0
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    incoming_time_var_sum += self.time_vars[d][intrip]
                    travel_time_sum += self.trip_vars[d][intrip] * intrip.lp.time
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    outgoing_time_var_sum += self.time_vars[d][otrip]
            self.mdl.add_constraint(incoming_time_var_sum + travel_time_sum <= outgoing_time_var_sum)
        log.info("Set incoming trip before outgoing trip constraints")

        for loc in self.request_nodes:
            driver_id_sum = 0
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    driver_id_sum += d.id * self.trip_vars[d][intrip]
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    driver_id_sum -= d.id * self.trip_vars[d][otrip]
            self.mdl.add_constraint(ct=driver_id_sum == 0)

        for rS in self.request_starts:
            rE = self.request_map[rS]
            driver_id_sum = 0
            for d in self.drivers:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[rE]):
                    driver_id_sum += d.id * self.trip_vars[d][intrip]
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[rS]):
                    driver_id_sum -= d.id * self.trip_vars[d][otrip]
            self.mdl.add_constraint(ct=driver_id_sum == 0)
        log.info("Set incoming driver is the same as outgoing driver constraints")

        """
        Capacity Constraints
        """
        for loc in self.request_nodes:
            incoming_capacity_filled = 0
            outgoing_capacity_filled = 0
            for d in self.drivers:
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    outgoing_capacity_filled += self.capacity_vars[d][otrip]
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    incoming_capacity_filled += self.capacity_vars[d][intrip]
            self.mdl.add_constraint(outgoing_capacity_filled == incoming_capacity_filled + self.node_capacities[loc])
        log.info("Set capacity value constraints")

        for d in self.drivers:
            for loc in self.driver_starts:
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[loc]):
                    self.mdl.add_constraint(ct=self.capacity_vars[d][otrip] == 0)
            for loc in self.driver_ends:
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[loc]):
                    self.mdl.add_constraint(ct=self.capacity_vars[d][intrip] == 0)
        log.info("Set initial and final trip capacity constraints")

        self.__add_custom_constraints()

    def __add_custom_constraints(self) -> None:
        """
        Add Custom Driver Fairness constraints.
        These are the key constraints that set apart this model.
        """
        log.info("Adding Custom Defined Constraints")

        """
        Route Length Penalty
        """
        for d in self.drivers:
            driver_departure_time = 0
            driver_return_time = 0
            for dS in self.driver_starts:
                if dS.get_clean_address() != d.get_clean_address():
                    continue
                for otrip in self.filter_driver_feasible_trips(d, self.outtrips[dS]):
                    driver_departure_time += self.time_vars[d][otrip]
                break
            for dE in self.driver_ends:
                if dE.get_clean_address() != d.get_clean_address():
                    continue
                for intrip in self.filter_driver_feasible_trips(d, self.intrips[dE]):
                    driver_return_time += self.time_vars[d][intrip]
                break
            self.obj += self.ROUTE_LIMIT_PEN * (driver_return_time - driver_departure_time)
            if not d.early_day_flag:
                try:
                    c = self.mdl.add_constraint(driver_departure_time >= self.EARLY_DAY_TIME)
                    self.early_day_constraints.add(c)
                    pass
                except DOcplexException as e:
                    if 'trivially' not in e.message:
                        raise e
                    log.info(f"Can't restrict early day for {d}")

        log.info("Set Route Length Penalty and Early Day constraints")
        """
        Merge Trip Requirements
        """
        for d in self.drivers:
            for mer in self.filter_driver_feasible_trips(d, self.merges):
                self.mdl.add_constraint(ct=self.trip_vars[d][mer] == self.trip_vars[d][self.merges[mer]])
                self.obj += self.MERGE_PEN * (self.time_vars[d][mer] - (
                            self.time_vars[d][self.merges[mer]] + self.merges[mer].lp.time * self.trip_vars[d][
                        mer])) * (24)

        log.info("Set merge trip constraints")

        """
        Equalizing Revenue Penalty
        """
        self.rev_max = self.mdl.continuous_var(0)
        self.rev_min = self.mdl.continuous_var(0)
        for d in self.drivers:
            self.revenue_vars[d] = self.mdl.continuous_var(lb=0, name="Revenue" + str(d.id))
            self.mdl.add_constraint(self.revenue_vars[d] == sum(self.revenues[t.lp.o] * self.trip_vars[d][t] for t in
                                                                self.filter_driver_feasible_trips(d,
                                                                                                  self.all_trips.values())))
            self.mdl.add_constraint(self.rev_max >= self.revenue_vars[d])
            self.mdl.add_constraint(self.rev_min <= self.revenue_vars[d])
        self.obj += self.REVENUE_PEN * (self.rev_max - self.rev_min)
        log.info("Set Revenue constraints")

        """
        Equalizing Wheel Chair Trip Penalty
        """
        self.max_wheelchair_trips = self.mdl.continuous_var(0)
        self.min_wheelchair_trips = self.mdl.continuous_var(0)
        for d in self.drivers:
            if 'W' not in d.level_of_service: continue
            self.wheelchair_vars[d] = self.mdl.continuous_var(lb=0, name="Wheelchairs" + str(d.id))
            self.mdl.add_constraint(self.wheelchair_vars[d] == sum(self.trip_vars[d][t] for t in
                                                                   filter(lambda x: x.required_level_of_service == 'W',
                                                                          self.filter_driver_feasible_trips(d,
                                                                                                            self.all_trips.values()))))
            self.mdl.add_constraint(self.max_wheelchair_trips >= self.wheelchair_vars[d])
            self.mdl.add_constraint(self.min_wheelchair_trips <= self.wheelchair_vars[d])
        self.obj += self.W_PEN * (self.max_wheelchair_trips - self.min_wheelchair_trips)
        log.info("Set Wheelchair trip fairness constraints")

    def __prepare_objective(self) -> None:
        """
        Objective function
        """
        for d, driver_trips in self.trip_vars.items():
            for t, var in driver_trips.items():
                self.obj += 1440 * t.lp.time * var
        log.info("Defined Objective Function")
        self.mdl.minimize(self.obj)

    def solve(self, solution_file: str, save_stages: bool = False) -> DataFrame:
        self.solution_df = None
        """TODO: Make this process of retrying solver better!!!"""
        for i in range(self.MAX_RETRIES):
            removed_early_day_constraints = False
            removed_single_rider_constraints = False
            try:
                progress_listener = TimeListener(self.STAGE1_TIME)
                self.mdl.add_progress_listener(progress_listener)
                first_solve = self.mdl.solve()
                if first_solve and (
                        first_solve.solve_status == JobSolveStatus.FEASIBLE_SOLUTION or first_solve.solve_status == JobSolveStatus.OPTIMAL_SOLUTION):
                    log.info(f"First solve status: {self.mdl.get_solve_status()}")
                    log.info(f"First solve obj value:  {self.mdl.objective_value}")
                    if save_stages: self.__save_solution(solution_file + '_stage1')
                    driver_miles = self.__calc_driver_miles()
                    log.info(f"Total Number of trip miles by each driver after stage 1: {driver_miles}")
                else:
                    log.info("Stage 1 Infeasible with Early Day constraints")
                if not first_solve or first_solve.solve_status == JobSolveStatus.INFEASIBLE_SOLUTION:
                    self.mdl.remove_progress_listener(progress_listener)
                    if self.STAGE1_GAP:
                        progress_listener = GapListener(self.STAGE1_TIME, self.STAGE1_GAP)
                    else:
                        progress_listener = TimeListener(self.STAGE1_TIME)
                    self.mdl.add_progress_listener(progress_listener)
                    log.info("Relaxing Early Day Constraints")
                    self.mdl.remove_constraints(self.early_day_constraints)
                    removed_early_day_constraints = True
                    first_solve = self.mdl.solve()
                    if first_solve and (
                            first_solve.solve_status == JobSolveStatus.FEASIBLE_SOLUTION or first_solve.solve_status == JobSolveStatus.OPTIMAL_SOLUTION):
                        log.info(f"First solve status (No Early Day constraints): {self.mdl.get_solve_status()}")
                        log.info(f"First solve obj value (No Early Day constraints): {self.mdl.objective_value}")
                        if save_stages: self.__save_solution(solution_file + '_stage1_no_ed')
                        driver_miles = self.__calc_driver_miles()
                        log.info(f"Total Number of trip miles by each driver after stage 1:  {driver_miles}")
                    else:
                        log.info("Stage 1 infeasible without early day constraints")
                log.info("Relaxing single rider requirements constraints")
                self.mdl.remove_constraints(self.single_rider_constraints)
                removed_single_rider_constraints = True
                log.info("Warm starting from single rider constrained solution")
                if first_solve:
                    self.mdl.add_mip_start(first_solve)
                self.mdl.remove_progress_listener(progress_listener)

                if self.STAGE2_GAP:
                    progress_listener = GapListener(self.STAGE2_TIME, self.STAGE2_GAP)
                else:
                    progress_listener = TimeListener(self.STAGE2_TIME)

                self.mdl.add_progress_listener(progress_listener)
                self.mdl.solve()
                log.info("Final solve status: {self.mdl.get_solve_status()}")
                log.info(f"Final Obj value: {self.mdl.objective_value}")
                log.info(f"Min Revenue: {self.rev_min.solution_value}")
                log.info(f"Max Revenue: {self.rev_max.solution_value}")
                log.info(f"Min W Trips: {self.min_wheelchair_trips.solution_value}")
                log.info(f"Max W Trips: {self.max_wheelchair_trips.solution_value}")
            except DOcplexException as e:
                log.info(f"{i}th solution did not work...trying again", exc_info=True)
                continue
            finally:
                self.__save_solution(solution_file)
                driver_miles = self.__calc_driver_miles()
                log.info(f"Total Number of trip miles by each driver: {driver_miles}")
                break
        if self.solution_df is None:
            raise SolutionNotFoundException(
                f"General Optimizer failed to find solution for {self.mdl.name} after {self.MAX_RETRIES} tries")

        return self.solution_df

    def __calc_driver_miles(self) -> Dict[Driver, float]:
        """
        Calculate the number of miles traveled by each driver
        :return: Mapping between driver and miles assigned to driver by solution
        """
        driverMiles = dict()
        for d, driver_trips in self.trip_vars.items():
            driverMiles[d] = 0
            for t, var in driver_trips.items():
                if self.trip_vars[d][t].solution_value >= 0.1:
                    driverMiles[d] += t.lp.miles
        return driverMiles

    def __save_solution(self, solution_file: str) -> None:
        """
        Write solution in CSV format to the
        :param solution_file: Path to where solution will be saved
        """

        def assigned_trip_generator():
            for d, driver_trips in self.trip_vars.items():
                for t, var in driver_trips.items():
                    if t.lp.o not in self.request_starts or var.solution_value != 1:
                        continue
                    yield (d, t)

        def debug_trip_generator(d):
            for t, var in self.trip_vars[d].items():
                if var.solution_value != 1:
                    continue
                yield (d, t)

        for dr in self.drivers:
            for d, t in sorted(debug_trip_generator(dr), key=lambda x: self.time_vars[x[0]][x[1]].solution_value):
                log.debug(f"{d.name}, {t.lp.o}, {t.lp.d}, {self.time_vars[d][t].solution_value}, {t.lp.time}")

        columns = ['trip_id', 'driver_id', 'driver_name', 'trip_date', 'trip_pickup_address', 'trip_pickup_time',
                   'est_pickup_time', 'trip_dropoff_address', 'trip_dropoff_time', 'est_dropoff_time', 'trip_los',
                   'est_miles', 'est_time', 'trip_rev']
        data = []
        for d, t in sorted(assigned_trip_generator(), key=lambda x: self.time_vars[x[0]][x[1]].solution_value):
            end_time = -1
            rE = self.request_map[t.lp.o]
            for intrip in self.filter_driver_feasible_trips(d, self.intrips[rE]):
                if self.trip_vars[d][intrip].solution_value == 1:
                    end_time = self.time_vars[d][intrip].solution_value + intrip.lp.time
                    if end_time < self.time_vars[d][t].solution_value + t.lp.time:
                        log.critical(f"Entering time (end_time) into request end ({rE}) earlier than departure time ({self.time_vars[d][t].solution_value}) from request start ({t.lp.o}) with a mininum travel time of {t.lp.time}")
                        incoming_trips_to_request_end = sum(self.trip_vars[d][intrip].solution_value for intrip in self.filter_driver_feasible_trips(d, self.intrips[rE]))
                        log.critical(f"Total Incoming Trips to request end {incoming_trips_to_request_end}")
                        log.critical(f"Outgoing trip from request start {t}, trip_id: {t.id} , start_time: {self.time_vars[d][t].solution_value}, travel time: {t.lp.time}")
                        log.critical(f"Incoming trip to request end {intrip}, trip_id: {intrip.id} , start_time: {self.time_vars[d][intrip].solution_value}, travel time: {intrip.lp.time}")
                    break
            if end_time < 0:
                log.critical(f"No end time found for trip starting from {t.lp.o} and ending at {rE}")
            required_end = self.all_trips[self.location_to_primary_trip_id_map[t.lp.o]].scheduled_dropoff
            ptrip = self.all_trips[self.location_to_primary_trip_id_map[t.lp.o]]
            data.append(
                [self.location_to_primary_trip_id_map[t.lp.o], d.id, d.name, self.date, t.lp.o.get_clean_address(),
                 t.scheduled_pickup, self.time_vars[d][t].solution_value, rE.get_clean_address(), required_end,
                 end_time,
                 t.required_level_of_service, ptrip.lp.miles, ptrip.lp.time, self.revenues[t.lp.o]])
        self.solution_df = pd.DataFrame(data, columns=columns)
        self.solution_df.to_csv(solution_file)
