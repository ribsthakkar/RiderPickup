import pandas as pd

from sqlalchemy import Column, Integer, String, Interval

from avicena.util.TimeWindows import get_time_window_by_hours_minutes
from .Database import Base

class MergeDetails(Base):
    __tablename__ = "merge_details"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    merge_window = Column(Interval)

def load_merge_details_from_db(session):
    return {row.address: row.merge_window for row in session.query(MergeDetails).all()}

def load_merge_details_from_csv(merge_details_file):
    return {row['address']: get_time_window_by_hours_minutes(0, int(row['window'])) for _, row in pd.read_csv(merge_details_file).iterrows()}