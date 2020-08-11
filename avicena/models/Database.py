from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

metadata = MetaData()
Base = declarative_base(metadata=metadata)


def create_db_session(db_config):
    url = db_config['url'].replace('//', f"//{db_config['username']}@{db_config['password']}")
    engine = create_engine(url)
    session = Session(engine)
    return session


def close_db_session(session):
    session.close()
