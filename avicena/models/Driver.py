from . import db

class Driver(db.Model):
    __tablename__ = "driver"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    address = db.Column(db.String, nullable=False)
    capacity = db.Column(db.Float, default=2.0)
    level_of_service = db.Column(db.String, nullable=False)
    early_day_flag = db.Column(db.Boolean, default=False)
    assignments = db.relationship('DriverAssignment', backref='driver')

    def create(self):
        db.session.add(self)
        db.session.commit()
        return self

    def __init__(self, id,  name, address, capacity, level_of_service, early_day_flag):
        self.id = int(id)
        self.name = name
        self.address = address
        self.capacity = capacity
        self.level_of_service = level_of_service
        self.early_day_flag = early_day_flag
    
    def __repr__(self):
        return '<Driver %s:%r>'.format(self.name, str(self.id))