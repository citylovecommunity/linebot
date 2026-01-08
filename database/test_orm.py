from base import SessionLocal
from models import Member


def test_connection():
    db = SessionLocal()
    try:
        # 1. Try to fetch one record
        user = db.query(Member).first()
        print(
            f"Connection Successful! Found user: {user.name if user else 'No users yet'}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    test_connection()
