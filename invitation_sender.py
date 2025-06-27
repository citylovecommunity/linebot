import os

import psycopg
from dotenv import load_dotenv

from util import get_user_id, load_bubble, send_bubble

# 1. 取得本次發送名單
# 2. 誰該在名單：sub_sent_at為空

load_dotenv()
DB = os.getenv('DB')
TEST_USER_ID = os.getenv("TEST_USER_ID")


def get_invitation_list():
    stmt = """
    select subject_id, object_id from 
    matching where sub_sent_at is null;
    """
    with psycopg.connect(DB) as conn:
        with conn.cursor() as cur:
            return cur.execute(stmt).fetchall()


def send_invitation(subject_id, object_id):
    # if沒綁定，傳line給相應負責人
    invitation_bubble = load_bubble('invitation.json')

    # invitation_bubble = bubble_modifier(invitation_bubble)

    user_id = get_user_id(subject_id)

    if user_id:
        send_bubble(TEST_USER_ID, invitation_bubble)
    else:
        # responsible_id = get_responsible_id(subject_id)
        # send_bubble(responsible_id, warning_bubble)
        print("bad_user")

    pass


def write_sent_to_db():
    pass


if __name__ == '__main__':
    print(get_invitation_list())
