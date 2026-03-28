
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from flask import g
from sqlalchemy.orm import Session


# 1. Define a global placeholder for the Session Factory
# We will fill this ONE TIME when the app starts.
_session_factory = None


def get_session_factory(database_url: str) -> Session:
    engine = create_engine(
        database_url,
        pool_pre_ping=True,   # Tests the connection before each query
        pool_recycle=300,     # Recreate connections older than 5 mins (Neon drops idle connections)
        connect_args={
            "connect_timeout": 10,    # Fail fast if Neon is unreachable
            "keepalives": 1,          # Enable TCP keepalives to detect dead connections
            "keepalives_idle": 10,    # Start probing after 10s idle
            "keepalives_interval": 2, # Probe every 2s
            "keepalives_count": 3,    # Give up after 3 failed probes (~16s total, not 27s)
        },
    )
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(app):
    """
    Call this function once in your main.py.
    It creates the Engine and Factory using the app's config.
    """
    global _session_factory

    # Get string from app config
    db_url = app.config.get("DB")

    _session_factory = get_session_factory(db_url)

    # Register the teardown function automatically
    app.teardown_appcontext(close_db)


def get_db() -> Session:
    """
    Call this in your routes. It creates a new session for the current request.
    """
    if 'db_session' not in g:
        if _session_factory is None:
            raise RuntimeError(
                "Database not initialized! Call init_db(app) first.")

        # Create a new session for this specific request
        g.db_session = _session_factory()

    return g.db_session


def close_db(e=None):
    """
    Automatically closes the session when the request ends.
    """
    db = g.pop('db_session', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            db.invalidate()
