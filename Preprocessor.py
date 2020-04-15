import pandas as pd

from Driver import Driver
from Trip import Trip, LocationPair, TripType
from constants import FIFTEEN


class TripPreprocess:

    @staticmethod
    def load_revenue_table(rev_table_file):
        rev_df = pd.read_csv(rev_table_file)
        table = {'A':dict(), 'W':dict(), 'A-EP':dict(), 'W-EP':dict()}
        for typ in table:
            details = rev_df[['Miles', typ]]
            for _, row in details.iterrows():
                table[typ][row['Miles']] = float(row[typ])
        return table


    @staticmethod
    def calc_revenue(table, miles, los):
        rates = table[los]
        if miles < 4:
            return rates['0']
        elif miles < 7:
            return rates['4']
        elif miles < 10:
            return rates['7']
        else:
            return rates['10'] + rates['>10'] * (miles - 10)

    @staticmethod
    def prepare_and_load_trips(trips_file, revenue_table, assumptions, processed_file_name='calc_trips.csv'):
        trip_df = pd.read_csv(trips_file)
        trips = []
        if "UNKNOWN_TIME_BUFFER" in assumptions:
            buffer = assumptions["UNKNOWN_TIME_BUFFER"]
            end_buffer = assumptions["UNKNOWN_TIME_DROP"]
        else:
            buffer = FIFTEEN * 10
            end_buffer = FIFTEEN * 8


        with open(processed_file_name, "w") as ct:
            ct.write("trip_id,customer_name,trip_pickup_time,trip_pickup_address,trip_dropoff_time,trip_dropoff_address,trip_los,"
                     "scheduled_miles, trip_miles,trip_rev,orig_lat,orig_long,dest_lat,dest_long,duration\n")
            for index, row in trip_df.iterrows():
                if not row['trip_status'] == "CANCELED":
                    o = row['trip_pickup_address'] + "P" + str(hash(row['trip_id']))[1:4]
                    d = row['trip_dropoff_address'] + "D" + str(hash(row['trip_id']))[1:4]
                    start = float(row['trip_pickup_time'])
                    end = float(row['trip_dropoff_time'])
                    los = row['trip_los']
                    cap = 1 if los == 'A' else 1.5
                    id = row['trip_id']

                    # Uknown Time Assumption
                    if start == 0.0 or end == 0.0 or start > 1 - (1/24):
                        start = float(trip_df.loc[trip_df['trip_id'] == id[:-1]+'A']['trip_dropoff_time']) + buffer
                        end = min(1 - (1/24), start + end_buffer)

                    # AB Merge Assumption
                    if "MERGE_ADDRESSES" in assumptions and (id[-1] == 'B' or id[-1] == 'C') and any(ad in row['trip_pickup_address'] for ad in assumptions['MERGE_ADDRESSES']):
                        if id[-1] == 'B':
                            start = float(trip_df.loc[trip_df['trip_id'] == id[:-1]+'A']['trip_dropoff_time']) + assumptions["MERGE_ADDRESS_WINDOW"]
                        elif id[-1] == 'C':
                            start = float(trip_df.loc[trip_df['trip_id'] == id[:-1]+'B']['trip_dropoff_time']) + assumptions["MERGE_ADDRESS_WINDOW"]
                        else:
                            print("Error processing merge Trip", id)
                            print(o, d, id, start, end)
                            exit(1)
                        typ = TripType.MERGE
                    else:
                        typ = None

                    # Revenue Calculation
                    rev = TripPreprocess.calc_revenue(revenue_table, int(row['trip_miles']), los)

                    t = Trip(o, d, cap, id, typ, start, end, rev, preset_miles=row['trip_miles'],prefix=False, suffix=True)
                    trips.append(t)
                    ct.write(",".join([t.id, '"' +  " ".join(row["customer_name"].split(",")) + '"', str(start),
                                       '"' + row['trip_pickup_address'] + '"',str(end) ,'"' + row['trip_dropoff_address'] + '"',
                                       los,str(row['trip_miles']), str(t.lp.miles), str(rev),str(t.lp.c1[0]), str(t.lp.c1[1]),
                                       str(t.lp.c2[0]), str(t.lp.c2[1]), str(t.lp.time)]) + "\n")
        return trips

    @staticmethod
    def load_trips(processed_trips_file='calc_trips.csv', assumptions=None):
        trip_df = pd.read_csv(processed_trips_file)
        trips = []
        for index, row in trip_df.iterrows():
            o = row['trip_pickup_address'] + "P" + str(hash(row['trip_id']))[1:4]
            d = row['trip_dropoff_address'] + "D" + str(hash(row['trip_id']))[1:4]
            start = float(row['trip_pickup_time'])
            end = float(row['trip_dropoff_time'])
            cap = 1 if row['trip_los'] == 'A' else 1.5
            id = row['trip_id']
            rev = float(row['trip_rev'])
            lp = LocationPair(o,d, (float(row['orig_lat']), float(row['orig_long'])), (float(row['dest_lat']), float(row['dest_long'])))
            # AB Merge Assumption
            if assumptions and "MERGE_ADDRESSES" in assumptions and (id[-1] == 'B' or id[-1] == 'C') and any( ad in o for ad in assumptions['MERGE_ADDRESSES']):
                typ = TripType.MERGE
            else:
                typ = None
            trips.append(Trip(o, d, cap, id, typ, start, end, rev, preset_miles=int(row['scheduled_miles']),lp=lp))
        return trips

    @staticmethod
    def load_drivers(drivers_file):
        driver_df = pd.read_csv(drivers_file)
        drivers = []
        for index, row in driver_df.iterrows():
            if row['Available?'] != 1:
                continue
            cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
            add = row['Address'] + "DR" + str(hash(row['ID']))[1:3]
            drivers.append(Driver(row['ID'], row['Name'], add, cap, row['Vehicle_Type']))
        return drivers
