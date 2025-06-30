import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import namedtuple_row
from util import get_user_id, load_bubble, send_bubble

# 1. 取得本次發送名單
# 2. 包裝泡泡
# 3. 發送
# 4. 修改db狀態

load_dotenv()
DB = os.getenv('DB')
TEST_USER_ID = os.getenv("TEST_USER_ID")
BUBBLE = load_bubble('invitation.json')


def get_list():
    stmt = """
    select id, subject_id, object_id from 
    matching where 
    current_state = 'invitation_sending';
    """
    with psycopg.connect(DB) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt).fetchall()


def bubble_modifier(subject_id, object_id):
    custom_bubble = BUBBLE.replace(...)
    return custom_bubble


def write_sent_to_db(matching_id):
    stmt = """
    update set current_state = 'invitation_waiting'
    where id = %s;
    """
    with psycopg.connect(DB) as conn:
        with conn.cursor() as cur:
            return cur.execute(stmt, (matching_id,))


def main():
    list_of_users = get_list()
    for row in list_of_users:
        bubble = bubble_modifier(row.subject_id, row.object_id)
        send_bubble(row.subject_id, bubble, '本週會員推薦🥰')
        write_sent_to_db(row.id)


if __name__ == '__main__':
    main()
