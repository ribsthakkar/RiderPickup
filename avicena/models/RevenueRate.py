import pandas as pd
from sqlalchemy import Column, Integer, String, Float

from .Database import Base

class RevenueRate(Base):
    __tablename__ = "revenue_rate"
    id = Column(Integer, primary_key=True)
    lower_mileage_bound = Column(Float, nullable=False)
    upper_mileage_bound = Column(Float, nullable=False)
    level_of_service = Column(String, nullable=False)
    revenue_per_mile = Column(Float, nullable=False)

    def __init__(self, lower_mileage_bound, upper_mileage_bound, level_of_service, revenue_per_mile):
        assert lower_mileage_bound < upper_mileage_bound
        self.lower_mileage_bound = lower_mileage_bound
        self.upper_mileage_bound = upper_mileage_bound
        self.level_of_service = level_of_service
        self.revenue_per_mile = revenue_per_mile

    def create(self, session):
        session.add(self)
        session.commit()
        return self


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
    table = {'A':dict(), 'W':dict(), 'A-EP':dict(), 'W-EP':dict()}
    for typ in table:
        details = rev_df[['Miles', typ]]
        for _, row in details.iterrows():
            table[typ][row['Miles']] = float(row[typ])
    return table
