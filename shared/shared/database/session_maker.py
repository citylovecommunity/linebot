from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def get_session_factory(database_url: str) -> Session:
    engine = create_engine(database_url,
                           pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
