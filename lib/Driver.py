class Driver:
    def __init__(self, id,  name, address, cap, los,ed):
        self.id = int(id)
        self.name = name
        self.address = address
        self.capacity = cap
        self.los = los
        self.ed = ed
    def __repr__(self):
        return str(self.id)