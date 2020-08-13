import datetime

import pandas as pd

from sqlalchemy import Column, Integer, String, Interval

from avicena.util.TimeWindows import get_time_window_by_hours_minutes
from . import Base


class MergeAddress(Base):
    __tablename__ = "merge_address"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    window = Column(Interval)

    def __init__(self, address, window):
        self.address = address
        self.window = window


def load_merge_details_from_db(session):
    return {row.address: row for row in session.query(MergeAddress).all()}


def load_merge_details_from_csv(merge_details_file):
    return {row['address']: MergeAddress(row['address'], datetime.timedelta(minutes=int(row['window']))) for _, row in
            pd.read_csv(merge_details_file).iterrows()}
