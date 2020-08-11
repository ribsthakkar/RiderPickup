from sqlalchemy import Column, Integer, String, Interval

from .Database import Base

class MergeDetails(Base):
    __tablename__ = "merge_details"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    merge_window = Column(Interval)

def load_merge_details_from_db(session):
    return {row.address: row.merge_window for row in session.query(MergeDetails).all()}
