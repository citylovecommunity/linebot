from config import BUBBLE_HERO_IMAGE_URL, FORM_WEB_URL
from utils import get_introduction_link, get_proper_name


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


def invitation_modifier(conn, base_bubble, matching_row):
    base_bubble = base_modifier(base_bubble)
    form_app_link = f'{FORM_WEB_URL}/{matching_row.access_token}/invitation'
    intro_link = get_introduction_link(conn, matching_row.object_id)
    obj_proper_name = get_proper_name(conn, matching_row.object_id)
    # get_icons()

    base_bubble = set_basic_bubble_title(base_bubble, '約會邀請卡')
    base_bubble = set_basic_bubble_city(base_bubble, matching_row.city)
    base_bubble = set_basic_bubble_name(base_bubble, obj_proper_name)
    base_bubble = set_basic_bubble_intro_link(base_bubble, intro_link)
    base_bubble = set_basic_bubble_form_link(
        base_bubble, form_app_link, '開啟邀請卡')

    return base_bubble


def liked_modifier(conn, base_bubble, matching_row):
    base_bubble = base_modifier(base_bubble)
    form_app_link = f'{FORM_WEB_URL}/{matching_row.access_token}/liked'
    intro_link = get_introduction_link(conn, matching_row.subject_id)
    sub_proper_name = get_proper_name(conn, matching_row.subject_id)

    # get_icons()
    base_bubble = set_basic_bubble_title(base_bubble, '約會回覆卡')
    base_bubble = set_basic_bubble_city(base_bubble, matching_row.city)
    base_bubble = set_basic_bubble_name(base_bubble, sub_proper_name)
    base_bubble = set_basic_bubble_intro_link(base_bubble, intro_link)
    base_bubble = set_basic_bubble_form_link(
        base_bubble, form_app_link, '開啟回覆卡')
    return base_bubble


def get_man_id(conn, matching_row):
    stmt = '''
    select gender from member
    where id = %s;
    '''
    with conn.cursor() as cur:
        result = cur.execute(stmt, (matching_row.subject_id,)).fetchone()
        if result and result[0][0] == 'M':
            return matching_row.subject_id
        else:
            return matching_row.object_id


def rest_r1_modifier(conn, base_bubble, matching_row):
    base_bubble = base_modifier(base_bubble)
    form_app_link = f'{FORM_WEB_URL}/{matching_row.access_token}/rest_r1'

    man_id = get_man_id(conn, matching_row)
    intro_link = get_introduction_link(conn, man_id)
    proper_name = get_proper_name(conn, man_id)

    # get_icons()
    base_bubble = set_basic_bubble_title(base_bubble, '餐廳選擇卡')
    base_bubble = set_basic_bubble_name(base_bubble, proper_name)
    base_bubble = set_basic_bubble_intro_link(base_bubble, intro_link)
    base_bubble = set_basic_bubble_form_link(
        base_bubble, form_app_link, '選擇餐廳')
    return base_bubble


BUBBLE_MODIFIER = {
    'invitation': invitation_modifier,
    'liked': liked_modifier,
    'rest_r1': rest_r1_modifier,

    # Add other bubble modifiers as needed
}
