from sqlalchemy import Column, Integer, DateTime, String, Interval, Float, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY as Array

from . import Base


class DriverAssignment(Base):
    """
    This class is responsible for holding the driver specific details for an assignment (i.e. details about trips
    assigned to a specific driver). These details include the coordinates for every location visited in order, the trip
    details for each trip the driver must complete, estimates for completing those trips, revenue from the trips, etc.
    It has a many to one relationship with an Assignment object and a many to one relationship with a driver object.
    It extends from the SQLAlchemy Base class as it is generated when an Assignment is produced by the model run, and
    it is stored in the database, if enabled.
    """
    __tablename__ = "driver_assignment"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime)
    driver_id = Column(Integer, ForeignKey("driver.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignment.id"), nullable=False)
    lats = Column(Array(Float))
    lons = Column(Array(Float))
    trip_ids = Column(Array(String))
    trip_pickup_addresses = Column(Array(String))
    trip_dropoff_addresses = Column(Array(String))
    trip_estimated_pickup_times = Column(Array(Interval))
    trip_scheduled_pickup_times = Column(Array(Interval))
    trip_estimated_dropoff_times = Column(Array(Interval))
    trip_scheduled_dropoff_times = Column(Array(Interval))
    trip_miles = Column(Array(Float))
    trip_los = Column(Array(String))
    trip_rev = Column(Array(Float))
