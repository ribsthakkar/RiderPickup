from typing import List, Dict, Any

from docplex.mp.model import Model
from pandas import DataFrame

from avicena.models import Trip, Driver


class BaseOptimizer:
    """
    This represents a BaseOptimizer class.
    Every optimizer must extend from BaseOptimizer, ensure the initialization details are filled, and implement the
    "solve" method.
    """
    def __init__(self, trips: List[Trip], drivers: List[Driver], name: str, date: str, speed: int, config: Dict[str, Any]) -> None:
        """
        Initialize the Model Base Optimizer. It also sets the configuration details used by all optimizers
        :param trips: List of valid Trip objects that were parsed and cleaned from the input file
        :param drivers: List of drivers selected to be dispatched for this model
        :param name: Name of the given model
        :param date: Date for which the model is running
        :param speed: Assumed travelling speed
        :param config: Required Configuration Details for all base optimizers
        """
        self.drivers_inp = drivers
        self.trips_inp = trips
        self.date = date
        self.mdl = Model(name=name)
        self.mdl.parameters.randomseed.set(config['seed'])
        self.SPEED = speed

    def solve(self, solution_file: str) -> DataFrame:
        """
        Solve the model
        :param solution_file: path to save solution details
        :return: DataFrame with the solution details
        """
        raise NotImplementedError("Solve must be implemented by child of BaseOptimizer")
