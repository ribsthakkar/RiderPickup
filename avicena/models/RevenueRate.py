import pandas as pd
from sqlalchemy import Column, Integer, String, Float

from . import Base

class RevenueRate(Base):
    __tablename__ = "revenue_rate"
    id = Column(Integer, primary_key=True)
    lower_mileage_bound = Column(Float, nullable=False)
    upper_mileage_bound = Column(Float, nullable=False)
    level_of_service = Column(String, nullable=False)
    base_rate = Column(Float, nullable=False)
    revenue_per_mile = Column(Float, nullable=False)

    def __init__(self, lower_mileage_bound, upper_mileage_bound, level_of_service, base_rate, revenue_per_mile):
        assert lower_mileage_bound < upper_mileage_bound
        self.lower_mileage_bound = lower_mileage_bound
        self.upper_mileage_bound = upper_mileage_bound
        self.level_of_service = level_of_service
        self.base_rate = base_rate
        self.revenue_per_mile = revenue_per_mile


def load_revenue_table_from_db(session):
    revenue_rates = session.query(RevenueRate).all()
    table = {}
    for revenue_rate in revenue_rates:
        if revenue_rate.level_of_service in table:
            table[revenue_rate.level_of_service].append(revenue_rate)
        else:
            table[revenue_rate.level_of_service] = [revenue_rate]
    return table


def load_revenue_table_from_csv(rev_table_file):
    rev_df = pd.read_csv(rev_table_file)
    table = {}
    for _, row in rev_df.iterrows():
        revenue_rate = RevenueRate(row['lower_mileage_bound'], row['upper_mileage_bound'], row['los'], float(row['base_rate']), float(row['rate_per_mile']))
        if revenue_rate.level_of_service in table:
            table[revenue_rate.level_of_service].append(revenue_rate)
        else:
            table[revenue_rate.level_of_service] = [revenue_rate]
    return table
