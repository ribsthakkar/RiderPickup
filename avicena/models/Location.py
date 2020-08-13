class Location:
    def __init__(self, addr, coord, suffix_len=0):
        self.addr = addr
        self.coord = coord
        self._suffix_len = suffix_len

    def __repr__(self):
        return self.addr + repr(self.coord)

    def get_clean_address(self):
        return self.addr[:-self._suffix_len] if self._suffix_len else self.addr

    def reversed_coord(self):
        return tuple(reversed(self.coord))