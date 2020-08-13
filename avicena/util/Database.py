from sqlalchemy.orm import Session
from sqlalchemy import create_engine


def create_db_session(db_config):
    engine = create_engine(db_config['url'])
    session = Session(engine)
    return session


def save_to_db_session(session, item):
    session.add(item)


def commit_db_session(session):
    session.commit()


def close_db_session(session):
    session.close()


def save_and_commit_to_db(session, item):
    save_to_db_session(session, item)
    commit_db_session(session)
    return item
