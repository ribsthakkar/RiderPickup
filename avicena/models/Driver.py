import datetime
import random
import pandas as pd
from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.orm import relationship

from .Database import Base

class Driver(Base):
    __tablename__ = "driver"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    capacity = Column(Float, default=2.0)
    level_of_service = Column(String, nullable=False)
    early_day_flag = Column(Boolean, default=False)
    assignments = relationship('DriverAssignment', backref='driver')

    def __init__(self, id,  name, address, capacity, level_of_service, early_day_flag):
        self.id = int(id)
        self.name = name
        self.address = address
        self.capacity = capacity
        self.level_of_service = level_of_service
        self.early_day_flag = early_day_flag

    def save_to_db(self, session):
        session.add(self)
        session.commit()
        return self

    def __repr__(self):
        return '<Driver %s:%r>'.format(self.name, str(self.id))

def load_drivers_from_db(session, driver_ids, date=None):
    db_drivers = list(map(session.query(Driver).get, driver_ids))
    drivers = []
    for index, d in enumerate(db_drivers):
        cap = 1 if d.level_of_service == 'A' else 1.5
        add = d.address + "DR" + str(hash(d.id))[1:3]
        if date is None:
            day_of_week = datetime.datetime.now().timetuple().tm_wday
        else:
            m, d, y = date.split('-')
            day_of_week = datetime.datetime(int(y), int(m), int(d)).timetuple().tm_wday
        early_day_flag = day_of_week % 2 != d.early_day_flag
        drivers.append(Driver(d.id, d.name, add, cap, d.level_of_service, early_day_flag))
    if not any(d.early_day_flag for d in drivers):
        x = random.choice(drivers)
        while x.early_day_flag:
            x = random.choice(drivers)
        x.early_day_flag = True
    return drivers


def load_drivers_from_csv(drivers_file, date=None):
    driver_df = pd.read_csv(drivers_file)
    drivers = []
    for index, row in driver_df.iterrows():
        if row['Available?'] != 1:
            continue
        cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
        add = row['Address'] + "DR" + str(hash(row['ID']))[1:3]
        if date is None:
            day_of_week = datetime.datetime.now().timetuple().tm_wday
        else:
            m, d, y = date.split('-')
            day_of_week = datetime.datetime(int(y), int(m), int(d)).timetuple().tm_wday
        early_day_flag = day_of_week % 2 != int(row['Early Day'])
        drivers.append(Driver(row['ID'], row['Name'], add, cap, row['Vehicle_Type'], early_day_flag))
    if not any(d.early_day_flag for d in drivers):
        x = random.choice(drivers)
        while x.early_day_flag:
            x = random.choice(drivers)
        x.early_day_flag = True
    return drivers