from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


def get_session_factory(database_url: str):
    engine = create_engine(database_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base = declarative_base()
