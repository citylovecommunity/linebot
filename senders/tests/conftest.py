import psycopg
import pytest
from config import DB


@pytest.fixture(scope="session")
def db_connection():
    conn = psycopg.connect(DB)
    yield conn
    conn.close()
