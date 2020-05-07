class Driver:
    def __init__(self, id,  name, address, cap, los):
        self.id = int(id)
        self.name = name
        self.address = address
        self.capacity = cap
        self.los = los
    def __repr__(self):
        return str(self.id)