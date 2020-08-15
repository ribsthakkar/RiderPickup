import datetime
import random
from typing import List, Iterable

import pandas as pd
from pandas import DataFrame
from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.orm import relationship, Session

from avicena.util.Exceptions import UnknownDriverException
from avicena.util.TimeWindows import date_to_day_of_week
from . import Base

class Driver(Base):
    """
    This class represents a Driver that could be available for dispatch to transport patients in the model.
    It holds information about the driver him/herself and details about their vehicle.
    It extends from the SQL Alchemy Base class as the the list of possible drivers is extracted from the
    database, if enabled.
    """
    __tablename__ = "driver"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    capacity = Column(Float, default=2.0)
    level_of_service = Column(String, nullable=False)
    alternate_early_day = Column(Boolean, default=False)
    assignments = relationship('DriverAssignment', backref='driver')

    def __init__(self, id: int, name: str, address: str, capacity:float, level_of_service:str, alternate_early_day: bool, suffix_len: int = 0):
        """
        Initializes a Driver object with relevant details.
        The suffix_len optional parameter indicates whether the address argument is provided with some suffix of
        characters.
        The suffix of characters is useful when trying to uniquely store/map driver addresses but the base addresses may
        be shared amongst drivers.
        :param id: Driver ID
        :param name: Driver Name
        :param address: Driver Address
        :param capacity: Total Capacity of the the driver's vehicle. Every wheel chair passenger takes 1.5 units of capacity.
                        Regular passanger takes 1
        :param level_of_service: The type of vehicle the driver has
        :param alternate_early_day: True if driver works early on T, Th, Sa. False if driver works early on M, W, F, Su
        :param suffix_len: Number of characters appended to base address
        """
        self.id = id
        self.name = name
        self.address = address
        self.capacity = capacity
        self.level_of_service = level_of_service
        self.alternate_early_day = alternate_early_day
        self.suffix_len = suffix_len

    def set_early_day_flag(self, flag: bool) -> None:
        """
        This function is only called during runtime to prepare the driver to be used in the optimizer model.
        When this function is called for a specific driver, it sets their early day flag to either True or False.
        :param flag: True if the driver is to be treated as available for the early day
        """
        self.early_day_flag = flag

    def get_clean_address(self) -> str:
        """
        Get the driver's address with the uniqueness suffix dropped, if there is one
        :return: Cleaned Address
        """
        return self.address[:-self.suffix_len] if self.suffix_len else self.address

    def __repr__(self) -> str:
        """
        :return: String representation of Driver
        """
        return f'<Driver {self.name}:{self.id}>'


def load_drivers_from_db(session: Session) -> List[Driver]:
    """
    Get all drivers from the database
    :param session:
    :return: List of Driver objects
    """
    return session.query(Driver).all()


def load_drivers_from_df(driver_df: DataFrame) -> List[Driver]:
    """
    Load driver objects from Pandas DataFrame
    :param driver_df: DataFrame with driver details
    :return: List of Driver objects
    """
    drivers = []
    for index, row in driver_df.iterrows():
        cap = 1 if row['Vehicle_Type'] == 'A' else 1.5
        alternate_early_day = bool(int(row['Early Day']))
        drivers.append(Driver(int(row['ID']), row['Name'], row['Address'], cap, row['Vehicle_Type'], alternate_early_day))
    return drivers


def load_drivers_from_csv(drivers_file: str):
    """
    Load driver objects from CSV
    :param drivers_file: Path to CSV file with driver details
    :return: List of Driver Objects
    """
    driver_df = pd.read_csv(drivers_file)
    return load_drivers_from_df(driver_df)


def prepare_drivers_for_optimizer(all_drivers: Iterable[Driver], driver_ids: Iterable[int], date: str = None):
    """
    Return a List of copied driver objects that have the early day flag enabled and an address with a suffix
    This copied list will be used for the
    :param all_drivers: List of Driver Objects loaded from the input
    :param driver_ids: Drivers whose copies will be made and returned
    :param date: Date in MM-DD-YYYY format
    :return: List of copied Driver objects to be used in the optimizer
    """
    all_ids = set(map(lambda x: x.id, all_drivers))
    for id in driver_ids:
        if id not in all_ids:
            raise UnknownDriverException(f"ID({id}) not found in drivers table")
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
