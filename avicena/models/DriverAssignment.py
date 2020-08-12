from sqlalchemy import Column, Integer, DateTime, String, Interval, Float, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY as Array

from .Database import Base

class DriverAssignment(Base):
    __tablename__ = "driver_assignment"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime)
    driver_id = Column(Integer, ForeignKey("driver.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignment.id"), nullable=False)
    lats = Column(Array(Float))
    lons = Column(Array(Float))
    trip_ids = Column(Array(String))
    trip_pu = Column(Array(String))
    trip_do = Column(Array(String))
    trip_est_pu = Column(Array(Interval))
    trip_sch_pu = Column(Array(Interval))
    trip_est_do = Column(Array(Interval))
    trip_sch_do = Column(Array(Interval))
    trip_miles = Column(Array(Float))
    trip_los = Column(Array(String))
    trip_rev = Column(Array(Float))

    def save_to_db(self, session):
        session.add(self)
        session.commit()
        return self