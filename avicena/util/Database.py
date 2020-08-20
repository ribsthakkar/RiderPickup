from typing import Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def create_db_session(db_config: Dict[str, Any]) -> Session:
    """
    Create a SQLAlchemy Database Connection session from to the database using the database configuration
    :param db_config: database specific section of the app_config.yaml
    :return: SQLAlchmey database connection
    """
    engine = create_engine(db_config['url'])
    session = Session(engine)
    return session


def save_to_db_session(session: Session, item: Any) -> None:
    """
    Stage an object to the session
    :param session: Database Connection Session
    :param item: Object to be added to session updates
    """
    session.add(item)


def commit_db_session(session: Session) -> None:
    """
    Commit session updates to database
    :param session: Database Connection Session
    """
    session.commit()


def close_db_session(session: Session) -> None:
    """
    Close database connection session
    :param session: Database Connection Session
    """
    session.close()


def save_and_commit_to_db(session: Session, item: Any):
    """
    Stage and commit and object to a database in one action
    :param session: Database connection session
    :param item: Object to add to database
    """
    save_to_db_session(session, item)
    commit_db_session(session)
    return item
