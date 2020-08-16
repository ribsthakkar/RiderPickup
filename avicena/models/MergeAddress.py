from typing import Dict

import pandas as pd

from sqlalchemy import Column, Integer, String, Interval
from datetime import timedelta

from sqlalchemy.orm import Session

from . import Base


class MergeAddress(Base):
    """
    This class holds the merge details for a given merge address.
    It stores some substring of an address associated with being a merge trip. In other words, when someone is dropped
    at a merge address, they are expected to be picked up within a given window. This window is the second field stored
    in this object.
    It extends from the SQLAlchemy Base class as the the list of merge addresses and is extracted from the database,
    if enabled.
    """
    __tablename__ = "merge_address"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    window = Column(Interval)

    def __init__(self, address: str, window: timedelta) -> None:
        """
        Initialize a MergeAddress object with details about the time window for pickup expected at the merge address
        :param address:
        :param window:
        """
        self.address = address
        self.window = window


def load_merge_details_from_db(session: Session) -> Dict[str, MergeAddress]:
    """
    Load the merge address details from the database
    :param session: SQLAlchemy database connection session
    :return: Dict mapping an address to its respective MergeAddress object
    """
    return {row.address: row for row in session.query(MergeAddress).all()}


def load_merge_details_from_csv(merge_details_file: str) -> Dict[str, MergeAddress]:
    """
    Load the merge address details from a CSV file
    :param merge_details_file: path to CSV containing merge details
    :return: Dict mapping an address to a MergeAddress object with its details
    """
    return {row['address']: MergeAddress(row['address'], timedelta(minutes=int(row['window']))) for _, row in
            pd.read_csv(merge_details_file).iterrows()}
