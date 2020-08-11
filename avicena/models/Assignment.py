from sqlalchemy import Column, Integer, DateTime, String, Interval, Float
from sqlalchemy.dialects.postgresql import ARRAY as Array
from sqlalchemy.orm import relationship

from .Database import Base

class Assignment(Base):
    __tablename__ = "assignment"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime)
    name = Column(String)
    driver_assignments = relationship('DriverAssignment', backref='assignment')
    drivers = Column(Array(String))
    driver_ids = Column(Array(Integer))
    trips = Column(Array(String))
    times = Column(Array(Interval))
    earliest_picks = Column(Array(Interval))
    latest_drops = Column(Array(Interval))
    miles = Column(Array(Float))
    revenues = Column(Array(Float))
    location_lats = Column(Array(Float))
    location_lons = Column(Array(Float))
    location_labels = Column(Array(String))

    def serialize(self):
        return {"id": self.id,
                "date": self.date,
                "name": self.name}

    def create(self, session):
        session.add(self)
        session.commit()
        return self
