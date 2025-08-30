import json
import copy


from config import ADMIN_LINE_ID, SENDER_PRODUCTION, TEST_USER_ID, line_bot_api, BUBBLE_HERO_IMAGE_URLs
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


def set_two_way_bubble_link_intro(conn, bubble, matching_row, message, info_title):
    bubble_for_obj = copy.deepcopy(bubble)
    bubble_for_sub = copy.deepcopy(bubble)

    # For Obj
    sub_intro_link = get_introduction_link(
        conn, matching_row.subject_id)
    sub_name = get_proper_name(conn, matching_row.subject_id)
    bubble_for_obj = set_basic_bubble(
        bubble_for_obj, info_title, matching_row.city, sub_name, sub_intro_link, message=message)

    # For Sub
    obj_intro_link = get_introduction_link(
        conn, matching_row.object_id)
    obj_name = get_proper_name(conn, matching_row.object_id)
    bubble_for_sub = set_basic_bubble(
        bubble_for_sub, info_title, matching_row.city, obj_name, obj_intro_link, message=message)

    return bubble_for_obj, bubble_for_sub


def base_modifier(base_bubble):
    # add universal settings
    base_bubble['hero']['url'] = BUBBLE_HERO_IMAGE_URL
    return base_bubble


def set_basic_bubble_title(bubble, title):
    bubble["body"]["contents"][0]['text'] = title
    return bubble


def set_basic_bubble_name(bubble, name):
    bubble["body"]["contents"][2]["contents"][1]["contents"][1]["text"] = name
    return bubble


def set_basic_bubble_city(bubble, name):
    bubble["body"]["contents"][2]["contents"][0]["contents"][1]["text"] = name
    return bubble


def set_basic_bubble_intro_link(bubble, link, label='介紹卡連結'):
    bubble["footer"]["contents"][0]["action"]["uri"] = link
    bubble["footer"]["contents"][0]["action"]["label"] = label
    return bubble


def set_basic_bubble_form_link(bubble, link, label):
    bubble["footer"]["contents"][1]["action"]["uri"] = link
    bubble["footer"]["contents"][1]["action"]["label"] = label
    return bubble


def set_basic_bubble_message(bubble, message):
    bubble["body"]["contents"][3]['text'] = message
    return bubble


def set_basic_bubble(bubble, title, city, name, intro_link, form_link=None, form_label=None, message=None):
    bubble = set_basic_bubble_title(bubble, title)
    bubble = set_basic_bubble_city(bubble, city)
    bubble = set_basic_bubble_name(bubble, name)
    bubble = set_basic_bubble_intro_link(bubble, intro_link)
    if form_link and form_label:
        bubble = set_basic_bubble_form_link(
            bubble, form_link, form_label)
    else:
        bubble = remove_form_link(bubble)
    if message:
        bubble = set_basic_bubble_message(
            bubble, message)
    else:
        bubble = remove_message(bubble)
    return bubble


def remove_message(bubble):
    bubble['body']['contents'].pop(-2)
    return bubble


def remove_form_link(bubble):
    bubble['footer']['contents'].pop(1)
    return bubble


def set_info_bubble(bubble, title, city, name, intro_link, message):
    bubble = set_basic_bubble_title(bubble, title)
    bubble = set_basic_bubble_city(bubble, city)
    bubble = set_basic_bubble_name(bubble, name)
    bubble["footer"]["contents"][1]["action"]["uri"] = intro_link
    bubble["footer"]["contents"][0]["text"] = message

    return bubble


def set_deal_bubble(bubble, city, name, rest_name, phone, message, time, rest_link, intro_link, cancel_link):
    bubble["body"]["contents"][2]["contents"][0]["contents"][1]["text"] = city
    bubble["body"]["contents"][2]["contents"][1]["contents"][1]["text"] = time
    bubble["body"]["contents"][2]["contents"][2]["contents"][1]["text"] = name
    bubble["body"]["contents"][2]["contents"][3]["contents"][1]["text"] = rest_name
    bubble["body"]["contents"][2]["contents"][4]["contents"][1]["text"] = phone
    bubble["body"]["contents"][2]["contents"][5]["contents"][1]["text"] = message
    bubble["footer"]["contents"][0]["action"]["uri"] = rest_link
    bubble["footer"]["contents"][1]["action"]["uri"] = intro_link
    bubble["footer"]["contents"][2]["action"]["uri"] = cancel_link
    return bubble


def change_state(conn, old_state, new_state, matching_id):
    with conn.cursor() as curr:
        stmt = """
        select current_state from matching where id=%s;
        """
        current_state = curr.execute(
            stmt, (matching_id,)).fetchone()
        if current_state != old_state:
            raise ValueError(
                f"{matching_id}狀態錯誤，預期{old_state}，但上面是{current_state}")

        stmt = """
            update matching set current_state = %s, updated_at = now() where id=%s;
            """
        curr.execute(
            stmt, (new_state, matching_id,))

        stmt = """
            insert into matching_state_history (matching_id, old_state, new_state, created_at)
            values (%s, %s, %s, now());
            """
        curr.execute(
            stmt, (matching_id, old_state, new_state))
