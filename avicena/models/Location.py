from typing import Tuple


class Location:
    """
    This class represents a single location. Every address (driver or trip) must have
    its own Location object despite potentially being the same as another address.
    """

    def __init__(self, addr: str, coord: Tuple[float, float], suffix_len: int = 0) -> None:
        """
        Initialize a Location Object
        :param addr: Address of Location
        :param coord: Coordinate tuple pair of location
        :param suffix_len: Length of suffix appended to the addr argument. This is to help uniquely
                            identify the Locations despite having the same address.
        """
        self.addr = addr
        self.coord = coord
        self._suffix_len = suffix_len

    def __repr__(self) -> str:
        """
        :return:  String representation of Location in <address_with_suffix>(coordinate) format
        """
        return self.addr + repr(self.coord)

    def get_clean_address(self) -> str:
        """
        :return:  Get the address with the suffix dropped if there is one
        """
        return self.addr[:-self._suffix_len] if self._suffix_len else self.addr

    def reversed_coord(self) -> Tuple[float, float]:
        """
        :return: Get the coordinates in reversed order.
        """
        return (self.coord[1], self.coord[0])
