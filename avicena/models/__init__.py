from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declarative_base

metadata = MetaData()
Base = declarative_base(metadata=metadata)

from .Driver import  Driver
from .Trip import Trip
from .Location import Location
from .LocationPair import LocationPair
from .Assignment import Assignment
from .DriverAssignment import DriverAssignment
from .RevenueRate import RevenueRate