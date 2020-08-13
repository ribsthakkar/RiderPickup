import datetime
import random
import pandas as pd
from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.orm import relationship

from avicena.util.Exceptions import UknownDriverException
from avicena.util.TimeWindows import date_to_day_of_week
from . import Base

class Driver(Base):
    __tablename__ = "driver"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    capacity = Column(Float, default=2.0)
    level_of_service = Column(String, nullable=False)
    alternate_early_day = Column(Boolean, default=False)
    assignments = relationship('DriverAssignment', backref='driver')

    def __init__(self, id,  name, address, capacity, level_of_service, alternate_early_day, suffix_len=0):
        self.id = id
        self.name = name
        self.address = address
        self.capacity = capacity
        self.level_of_service = level_of_service
        self.alternate_early_day = alternate_early_day
        self.suffix_len = suffix_len

    def set_early_day_flag(self, flag):
        self.early_day_flag = flag

    def get_clean_address(self):
        return self.address[:-self.suffix_len] if self.suffix_len else self.address

    def __repr__(self):
        return f'<Driver {self.name}:{self.id}>'


def load_drivers_from_db(session):
    return session.query(Driver).all()


def load_drivers_from_df(driver_df):
    drivers = []
    for index, row in driver_df.iterrows():
        cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
        alternate_early_day = int(row['Early Day'])
        drivers.append(Driver(int(row['ID']), row['Name'], row['Address'], cap, row['Vehicle_Type'], alternate_early_day))
    return drivers


def load_drivers_from_csv(drivers_file):
    driver_df = pd.read_csv(drivers_file)
    return load_drivers_from_df(driver_df)


def prepare_drivers_for_optimizer(all_drivers, driver_ids, date=None):
    all_ids = set(map(lambda x: x.id, all_drivers))
    for id in driver_ids:
        if id not in all_ids:
            raise UknownDriverException(f"ID({id}) not found in drivers table")
    output_drivers = []
    for index, d in enumerate(all_drivers):
        if d.id not in driver_ids: continue
        cap = 1 if d.level_of_service == 'A' else 1.5
        add = d.address + "DR" + str(hash(d.id))[1:3]
        day_of_week = date_to_day_of_week(date)
        output_drivers.append(Driver(d.id, d.name, add, cap, d.level_of_service, d.alternate_early_day, suffix_len=4))
        output_drivers[-1].set_early_day_flag(day_of_week % 2 != d.alternate_early_day)
    if not any(d.early_day_flag for d in output_drivers):
        x = random.choice(output_drivers)
        while x.early_day_flag:
            x = random.choice(output_drivers)
        x.set_early_day_flag = True
    return output_drivers
