import copy
import json
from collections import namedtuple
from datetime import datetime

from config import ADMIN_LINE_ID, SENDER_PRODUCTION, TEST_USER_ID, line_bot_api
from linebot.models import FlexSendMessage, TextMessage


def write_sent_to_db(conn, matching_id, body, send_to):
    history_stmt = """
    insert into sending_history (matching_id, body, send_at, send_to)
    values (%s, %s, now(), %s)
    """
    send_at_stmt = """
    update matching set last_sent_at = now() where id = %s
    """
    with conn.cursor() as cur:
        cur.execute(history_stmt, (matching_id, body,  send_to))
        cur.execute(send_at_stmt, (matching_id,))
    conn.commit()


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


def load_bubble_raw(name):
    with open('bubbles/'+name) as file:
        bubble = file.read()
    return BUBBLE(bubble)


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
    # 如果是女的，回傳盲約網址

    with conn.cursor() as curr:
        stmt = """
        select 
        case when gender = 'M' then
            user_info ->> '會員介紹頁網址'
        else then 
            user_info ->> '盲約介紹卡一'
        end
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


def get_phone_number(conn, member_id):
    stmt = """
    select phone_number from
    member
    where id = %s;
    """
    with conn.cursor() as cur:
        result = cur.execute(stmt, (member_id,)).fetchone()
        return result[0] if result else ''


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


real_sending_info = namedtuple(
    'real_sending_info', ['body', 'send_to'])


def send_bubble_to_member_id(conn, member_id, bubble, alt_text='嘻嘻', production=SENDER_PRODUCTION):
    user_id = get_user_id(conn, member_id)
    body = bubble
    if production:
        if user_id:
            #
            # send_bubble(user_id[0], bubble, alt_text)
            pass
        else:
            name = get_user_name(conn, member_id)
            body = f'會員 {name} 沒有綁定 LINE 帳號⚠️⚠️⚠️'
            user_id = ADMIN_LINE_ID
            line_bot_api.push_message(user_id,
                                      TextMessage(
                                          text=body,
                                          alt_text=alt_text,
                                      ))
    else:
        user_id = TEST_USER_ID
        send_bubble(TEST_USER_ID, body, alt_text)

    return real_sending_info(body_to_str(body), user_id)


def body_to_str(body):
    if isinstance(body, str):
        return body
    elif isinstance(body, dict):
        return json.dumps(body, ensure_ascii=False)
    else:
        return ''


def send_normal_text(conn, member_id, message, production=SENDER_PRODUCTION):
    user_id = get_user_id(conn, member_id)
    if production:
        if user_id:
            line_bot_api.push_message(user_id[0], TextMessage(text=message))
        else:
            name = get_user_name(conn, member_id)
            user_id = ADMIN_LINE_ID
            line_bot_api.push_message(ADMIN_LINE_ID, TextMessage(
                text=f'會員 {name} 沒有綁定 LINE 帳號⚠️⚠️⚠️',
            ))
    else:
        user_id = TEST_USER_ID
        line_bot_api.push_message(TEST_USER_ID, TextMessage(text=message))

    return real_sending_info(message, user_id)


class BUBBLE:
    def __init__(self, bubble):
        self.bubble = bubble

    def copy(self):
        return BUBBLE(copy.deepcopy(self.bubble))

    def set_title(self, title):
        self.bubble = self.bubble.replace('##標題##', title)
        return self

    def set_city(self, city):
        self.bubble = self.bubble.replace('##城市##', city)
        return self

    def set_time(self, time):
        self.bubble = self.bubble.replace('##時間##', time)
        return self

    def set_date(self, time):
        self.bubble = self.bubble.replace('##日期##', time)
        return self

    def set_book_name(self, book_name):
        self.bubble = self.bubble.replace('##訂位名字##', book_name)
        return self

    def set_book_phone(self, book_phone):
        self.bubble = self.bubble.replace('##訂位電話##', book_phone)
        return self

    def set_message(self, message):
        self.bubble = self.bubble.replace('##約會留言##', message)
        return self

    def set_bubble_message(self, message):
        self.bubble = self.bubble.replace('##message##', message)
        return self

    def set_intro_link(self, intro_link):
        self.bubble = self.bubble.replace('http://intro_url', intro_link)
        return self

    def set_sent_to_proper_name(self, name):
        self.bubble = self.bubble.replace('##對象##', name)
        return self

    def set_rest_name(self, rest_name):
        self.bubble = self.bubble.replace('##約會餐廳##', rest_name)
        return self

    def set_rest_url(self, rest_url):
        self.bubble = self.bubble.replace('http://rest_url', rest_url)
        return self

    def set_title(self, title):
        self.bubble = self.bubble.replace('##標題##', title)
        return self

    def set_form_app_link(self, form_app_link):
        self.bubble = self.bubble.replace(
            'http://form_app_url', form_app_link)
        return self

    def as_dict(self):
        return json.loads(self.bubble)


def change_state(conn, old_state, new_state, matching_id):
    with conn.cursor() as curr:
        stmt = """
        select current_state from matching where id=%s;
        """
        current_state = curr.execute(
            stmt, (matching_id,)).fetchone()[0]

        # if old_state is str, compare. If old state is tuple, check if current_state in it.
        if isinstance(old_state, tuple):
            if current_state not in old_state:
                raise ValueError(
                    f"{matching_id}狀態錯誤，預期{old_state}其中一個，但上面是{current_state}")
        elif current_state != old_state:
            raise ValueError(
                f"{matching_id}狀態錯誤，預期{old_state}，但上面是{current_state}")

        stmt = """
            update matching set 
            last_change_state_at=now(), 
            current_state = %s,
            updated_at = now() where id=%s;
            """
        curr.execute(
            stmt, (new_state, matching_id,))

        stmt = """
            insert into matching_state_history (matching_id, old_state, new_state, created_at)
            values (%s, %s, %s, now());
            """
        curr.execute(
            stmt, (matching_id, old_state, new_state))


def show_google_map_name(url):
    import requests
    from bs4 import BeautifulSoup

    response = requests.get(url, allow_redirects=True)
    soup = BeautifulSoup(response.text, 'html.parser')
    meta_tag = soup.find('meta', property='og:title')
    if meta_tag and meta_tag.get('content'):
        shop_name = meta_tag['content']
        return shop_name
    else:
        return None
