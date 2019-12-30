class Driver:
    def __init__(self, id,  name, address, cap):
        self.id = int(id)
        self.name = name
        self.address = address
        self.capacity = cap
    def __repr__(self):
        return str(self.id)