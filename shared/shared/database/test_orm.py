from shared.database.session_maker import SessionLocal
from models import Line_Info, Matching, Member


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


def test_relationship():
    db = SessionLocal()

    try:
        # 1. Try to fetch one record
        user = db.query(Member).join(Line_Info).first()

        print(
            f"Connection Successful! Found user: {user.name if user else 'No users yet'} with line_info {user.line_info.user_id}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


def test_matching():
    db = SessionLocal()

    try:
        # 1. Try to fetch one record
        matching = db.query(Matching).first()

        print(
            f"id={matching.id}, {matching.subject.name} 配 {matching.object.name}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    test_matching()
