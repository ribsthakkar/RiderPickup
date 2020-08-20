class InvalidTripException(Exception):
    """
    Raised if trip is trivially infeasible when constructed
    """
    pass


class InvalidConfigException(Exception):
    """
    Raised when there is an issue with the configuration
    """
    pass


class RevenueCalculationException(Exception):
    """
    Raised when Revenue Table is missing the level of service for a trip
    """
    pass


class SolutionNotFoundException(Exception):
    """
    Raised when the Optimizer could not find a solution after N attempts
    """
    pass


class UnknownDriverException(Exception):
    """
    Raised when a driver ID was passed in that was not part of the original CSV or Database set of drivers
    """
    pass


class MissingTripDetailsException(Exception):
    """
    Raised when the Trip Dataframe is missing necessary details
    """
    pass


class InvalidRevenueRateMileageException(Exception):
    """
    Raised with there is an issue with the revenue calculation. (i.e. there is not mileage window for the input number
    of miles)
    """
    pass


class DuplicateAddressException(Exception):
    """
    Raised when the same address string is found in a data structure expecting unique addresses
    """
    pass


class InvalidSolutionException(Exception):
    """
    Raised when sanity checks on solution produced by model are failing.
    """
    pass
