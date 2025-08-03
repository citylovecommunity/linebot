import json

from linebot.models import FlexSendMessage
from psycopg.rows import namedtuple_row
from config import FORM_WEB_URL, line_bot_api


def get_invitation_link(row):
    token = row.access_token
    return f'{FORM_WEB_URL}/{token}/invitation'


def get_introduction_link(conn, row):
    with conn.cursor() as curr:
        stmt = """
        select user_info ->> '會員介紹頁網址'
        from member
        where id = %s
        """
        result = curr.execute(stmt, (row.object_id, )).fetchone()
    return result[0] if result else ''


def get_obj_proper_name(conn, row):
    return get_proper_name(conn, row.object_id)


def get_icons():
    pass


def send_bubble_to_sub(conn, member_id, bubble, alt_text):
    user_id = get_user_id(conn, member_id)
    if user_id:
        send_bubble(user_id, bubble, alt_text)
    else:
        # send to administrator if no user_id found
        res_id = get_responsible_id(conn, member_id)
        base_bubble = load_bubble('no_user_id_warning')
        bubble = no_user_id_warning_modify(base_bubble, member_id)
        send_bubble(res_id, bubble, alt_text)


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


def get_proper_name(conn, member_id):
    stmt = """
    select name, gender from
    member
    where id = %s;
    """
    with conn.cursor() as cur:
        result = cur.execute(stmt, (member_id,)).fetchone()
        if result[1][0] == 'M':
            return f'{result[0][0]}先生'
        elif result[1][0] == 'F':
            return f'{result[0][0]}小姐'
        else:
            return ''


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


def send_bubble(user_id, bubble, alt_text='酷喔'):
    flex_message = FlexSendMessage(
        alt_text=alt_text,
        contents=bubble
    )
    line_bot_api.push_message(user_id, flex_message)


def load_bubble(name):
    with open('bubbles/'+name) as file:
        bubble = json.load(file)
    return bubble
