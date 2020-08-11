class Location:
    def __init__(self, addr, coord):
        self.addr = addr
        self.coord = coord

    def reversed_coord(self):
        return tuple(reversed(self.coord))