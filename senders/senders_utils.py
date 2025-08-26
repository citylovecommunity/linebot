import json

from config import ADMIN_LINE_ID, SENDER_PRODUCTION, TEST_USER_ID, line_bot_api
from linebot.models import FlexSendMessage, TextMessage


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


def get_gender_id(conn, matching_row, gender):
    stmt = '''
    select gender from member
    where id = %s;
    '''
    with conn.cursor() as cur:
        result = cur.execute(stmt, (matching_row.subject_id,)).fetchone()
        if result and result[0][0] == gender:
            return matching_row.subject_id
        else:
            return matching_row.object_id


def get_introduction_link(conn, member_id):
    with conn.cursor() as curr:
        stmt = """
        select user_info ->> '會員介紹頁網址'
        from member
        where id = %s
        """
        result = curr.execute(stmt, (member_id, )).fetchone()
    return result[0] if result else ''


def get_user_name(conn, member_id):
    stmt = """
    select name from
    member
    where id = %s;
    """
    with conn.cursor() as cur:
        result = cur.execute(stmt, (member_id,)).fetchone()
        return result[0] if result else '未知會員'


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


def send_bubble_to_member_id(conn, member_id, bubble, alt_text='嘻嘻', production=SENDER_PRODUCTION):
    user_id = get_user_id(conn, member_id)
    if production:
        if user_id:
            #
            # send_bubble(user_id[0], bubble, alt_text)
            pass
        else:
            name = get_user_name(conn, member_id)
            line_bot_api.push_message(ADMIN_LINE_ID, TextMessage(
                text=f'會員 {name} 沒有綁定 LINE 帳號⚠️⚠️⚠️',
                alt_text=alt_text,
            ))
    else:
        send_bubble(TEST_USER_ID, bubble, alt_text)


def send_normal_text(conn, member_id, message, production=SENDER_PRODUCTION):
    user_id = get_user_id(conn, member_id)
    if production:
        if user_id:
            line_bot_api.push_message(user_id[0], TextMessage(text=message))
        else:
            name = get_user_name(conn, member_id)
            line_bot_api.push_message(ADMIN_LINE_ID, TextMessage(
                text=f'會員 {name} 沒有綁定 LINE 帳號⚠️⚠️⚠️',
            ))
    else:
        line_bot_api.push_message(TEST_USER_ID, TextMessage(text=message))
