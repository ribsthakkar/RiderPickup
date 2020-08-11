from sqlalchemy.dialects.postgresql import ARRAY as Array
from . import db

class Assignment(db.Model):
    __tablename__ = "assignment"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    name = db.Column(db.String)
    driver_assignments = db.relationship('DriverAssignment', backref='assignment')
    drivers = db.Column(Array(db.String))
    driver_ids = db.Column(Array(db.Integer))
    trips = db.Column(Array(db.String))
    times = db.Column(Array(db.Interval))
    earliest_picks = db.Column(Array(db.Interval))
    latest_drops = db.Column(Array(db.Interval))
    miles = db.Column(Array(db.Float))
    revenues = db.Column(Array(db.Float))

    location_lats = db.Column(Array(db.Float))
    location_lons = db.Column(Array(db.Float))
    location_labels = db.Column(Array(db.String))

    def serialize(self):
        return {"id": self.id,
                "date": self.date,
                "name": self.name}

    def create(self):
        db.session.add(self)
        db.session.commit()
        return self
