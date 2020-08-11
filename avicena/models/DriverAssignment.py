from sqlalchemy.dialects.postgresql import ARRAY as Array
from . import db

class DriverAssignment(db.Model):
    __tablename__ = "driver_assignment"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    driver_id = db.Column(db.Integer, db.ForeignKey("driver.id"), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignment.id"), nullable=False)
    lats = db.Column(Array(db.Float))
    lons = db.Column(Array(db.Float))
    trip_ids = db.Column(Array(db.String))
    trip_pu = db.Column(Array(db.String))
    trip_do = db.Column(Array(db.String))
    trip_est_pu = db.Column(Array(db.Interval))
    trip_sch_pu = db.Column(Array(db.Interval))
    trip_est_do = db.Column(Array(db.Interval))
    trip_sch_do = db.Column(Array(db.Interval))
    trip_miles = db.Column(Array(db.Float))
    trip_los = db.Column(Array(db.String))
    trip_rev = db.Column(Array(db.Float))

    def create(self):
        db.session.add(self)
        db.session.commit()
        return self