import argparse
import json
import os

import psycopg
from linebot import LineBotApi
from linebot.models import FlexSendMessage
from psycopg.rows import namedtuple_row

# 1. 取得本次發送名單
# 2. 包裝泡泡
# 3. 發送
# 4. 修改db狀態

DB = os.getenv('DB')
TEST_USER_ID = os.getenv("TEST_USER_ID")
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))


def load_bubble(name):
    with open('bubbles/'+name) as file:
        bubble = json.load(file)
    return bubble


def send_bubble(user_id, bubble, alt_text='酷喔'):
    flex_message = FlexSendMessage(
        alt_text=alt_text,
        contents=bubble
    )
    line_bot_api.push_message(user_id, flex_message)


def no_user_id_warning_modify(base_bubble):
    pass


def send_bubble_to_sub(conn, member_id, bubble, alt_text):
    user_id = get_user_id(conn, member_id)
    if user_id:
        send_bubble(user_id, bubble, alt_text)
    else:
        res_id = get_responsible_id(conn, member_id)
        base_bubble = load_bubble('no_user_id_warning')
        bubble = no_user_id_warning_modify(base_bubble, member_id)
        send_bubble(res_id, bubble, alt_text)


def get_responsible_id(conn, member_id):
    stmt = """
    select user_id from
    line_info li
    join member m
    on li.phone_number = m.phone_number
    where m.name =  ...
    """
    with conn.cursor() as cur:
        result = cur.execute(stmt, (member_id,)).fetchone()
        return result


def get_user_id(conn, member_id):
    stmt = """
    select user_id from
    line_info li
    join member m
    on li.phone_number = m.phone_number
    where m.id = %s
    """
    with conn.cursor() as cur:
        result = cur.execute(stmt, (member_id,)).fetchone()
        return result


def get_list(conn, state):
    stmt = """
    select * from
    matching where
    current_state = %s;
    """
    with conn.cursor(row_factory=namedtuple_row) as cur:
        return cur.execute(stmt, (state+'_sending',)).fetchall()


def write_sent_to_db(conn, matching_id, state):
    stmt = """
    update set current_state = %s
    where id = %s;
    """
    with conn.cursor() as cur:
        return cur.execute(stmt, (state+'_waiting', matching_id,))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('state')
    args = parser.parse_args()

    state = args.state
    base_bubble = load_bubble(state+'.json')
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, state)
        for row in list_of_users:
            bubble = BUBBLE_MODIFIER[state](base_bubble)
            send_bubble_to_sub(row.subject_id, bubble, '本週會員推薦🥰')
            write_sent_to_db(conn, row.id, state)


if __name__ == '__main__':
    main()
