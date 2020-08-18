from typing import Dict, List

import pandas as pd
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import Session

from avicena.util.Exceptions import InvalidRevenueRateMileageException
from . import Base


class RevenueRate(Base):
    """
    This class represents the revenue details associated with a travel distance in miles and the level of service.
    It stores a lower travel distance bound, upper travel distance bound, a base rate, a rate per mile, and a specific
    level of service.
    It extends from the SQLAlchemy Base class as the revenue rates are polled from the database, if enabled.
    """
    __tablename__ = "revenue_rate"
    id = Column(Integer, primary_key=True)
    lower_mileage_bound = Column(Float, nullable=False)
    upper_mileage_bound = Column(Float, nullable=False)
    level_of_service = Column(String, nullable=False)
    base_rate = Column(Float, nullable=False)
    revenue_per_mile = Column(Float, nullable=False)

    def __init__(self, lower_mileage_bound: float, upper_mileage_bound: float, level_of_service: str, base_rate: float,
                 revenue_per_mile: float) -> None:
        """
        Inititalize a RevenueRate object with the neccessary details to compute revenue earned
        :param lower_mileage_bound: Lower bound (inclusive) for with the rate applies
        :param upper_mileage_bound: Upper bound (inclusive) for which the rate applies
        :param level_of_service: The level of service for which these bounds apply
        :param base_rate: the flat revenue earned for being in this mileage range
        :param revenue_per_mile: the per mile revenue made for being in this mileage range
        """
        assert lower_mileage_bound < upper_mileage_bound
        self.lower_mileage_bound = lower_mileage_bound
        self.upper_mileage_bound = upper_mileage_bound
        self.level_of_service = level_of_service
        self.base_rate = base_rate
        self.revenue_per_mile = revenue_per_mile

    def calculate_revenue(self, miles: float) -> float:
        """
        :param miles: distance for which revenue is being calculated
        :return: revenue made for trip with given distance
        """
        if self.lower_mileage_bound <= miles <= self.upper_mileage_bound:
            raise InvalidRevenueRateMileageException(
                f"{miles} miles not within RevenueRate bounds [{self.lower_mileage_bound},{self.upper_mileage_bound}]")
        return self.base_rate + self.revenue_per_mile * miles


def load_revenue_table_from_db(session: Session) -> Dict[str, List[RevenueRate]]:
    """
    Load Revenue Rates from database
    :param session: SQLAlchemy database connection session
    :return: Dict that maps level of service to a list of revenue rates
    """
    revenue_rates = session.query(RevenueRate).all()
    table = {}
    for revenue_rate in revenue_rates:
        if revenue_rate.level_of_service in table:
            table[revenue_rate.level_of_service].append(revenue_rate)
        else:
            table[revenue_rate.level_of_service] = [revenue_rate]
    return table


def load_revenue_table_from_csv(rev_table_file: str) -> Dict[str, List[RevenueRate]]:
    """
    Load RevenueRates from CSV file
    :param rev_table_file: path to CSV file
    :return: Dict that maps level of service to a list of revenue rates
    """
    rev_df = pd.read_csv(rev_table_file)
    table = {}
    for _, row in rev_df.iterrows():
        revenue_rate = RevenueRate(float(row['lower_mileage_bound']), float(row['upper_mileage_bound']), row['los'],
                                   float(row['base_rate']), float(row['rate_per_mile']))
        if revenue_rate.level_of_service in table:
            table[revenue_rate.level_of_service].append(revenue_rate)
        else:
            table[revenue_rate.level_of_service] = [revenue_rate]
    return table
