from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declarative_base

metadata = MetaData()
Base = declarative_base(metadata=metadata)

from . import Assignment, Driver, DriverAssignment, Location, LocationPair, MergeAddress, RevenueRate, Trip