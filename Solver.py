import pandas as pd

from Driver import Driver
from Trip import Trip


class TripCalculator:
    def __init__(self, trips_file, drivers_file, pricing_file = None, assuptions_file = None):
        self.trip_df = pd.read_csv(trips_file, keep_default_na=False)
        self.driver_df = pd.read_csv(drivers_file, keep_default_na=False)
        if pricing_file:
            self.pricing = pd.read_csv(pricing_file, keep_default_na=False)
        if assuptions_file:
            self.assumptions = pd.read_csv(assuptions_file, keep_default_na=False)
        self.trips = list(self.__prepare_trips())
        self.drivers = list(self.__prepare_drivers())

    def __prepare_trips(self):
        with open("calc_trips.csv", "w") as ct:
            ct.write("trip_pickup_time,trip_id,customer_name,trip_pickup_address,trip_dropoff_address,trip_los,"
                     "trip_miles,trip_rev,orig_lat,orig_log,dest_lat,dest_long,duration\n")
            for index, row in self.trip_df.iterrows():
                if not row['trip_status'] == "CANCELED":
                    o = row['trip_pickup_address'] + "P" + str(hash(row['trip_id']))[1:4]
                    d = row['trip_dropoff_address'] + "D" + str(hash(row['trip_id']))[1:4]
                    start = float(row['trip_pickup_time'])
                    end = float(row['trip_dropoff_time'])
                    if end == 0.0:
                        end = 1.0
                    cap = 1 if row['trip_los'] == 'A' else 1.5
                    id = row['trip_id']
                    t = Trip(o, d, cap, id, type, start, end, False, True)
                    if id == None:
                        print(o,d)
                    ct.write(",".join([str(row['trip_pickup_time']), t.id, '"' +  " ".join(row["customer_name"].split(",")) + '"',
                                       '"' + row['trip_pickup_address'] + '"', '"' + row['trip_dropoff_address'] + '"',
                                       row['trip_los'], str(t.lp.miles), '0',str(t.lp.c1[0]), str(t.lp.c1[1]),
                                       str(t.lp.c2[0]), str(t.lp.c2[1]), str(t.lp.time)]) + "\n")
                    yield t

    def __prepare_drivers(self):
        for index, row in self.driver_df.iterrows():
            if row['Available?'] != str(1):
                continue
            cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
            add = row['Address'] + "DR" + str(hash(row['ID']))[1:3]
            yield Driver(row['ID'], row['Name'], add, cap, row['Vehicle_Type'])

    def prepare_model(self, optimizer, optimzer_params):
        self.optimzer = optimizer(self.trips, self.drivers, optimzer_params)
        return self.optimzer

    def solve(self, solution_file=None):
        return self.optimzer.solve(solution_file)

    def visualize(self, solution_file, save_maps=False):
        self.optimzer.visualize(solution_file, save_maps)

class TripSolution:
    def __init__(self, trips):
        self.driver_route = dict()
        self.primary_trip_assignments = dict()
