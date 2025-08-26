import copy
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import List

from config import BUBBLE_HERO_IMAGE_URL, FORM_WEB_URL
from senders_utils import (get_gender_id, get_introduction_link,
                           get_proper_name, load_bubble,
                           send_bubble_to_member_id)

SendingInfo = namedtuple('SendingInfo', ['recipient', 'bubble', 'alt'])


class Sender(ABC):
    OLD_STATE = None
    NEW_STATE = None
    NOTIFICATION = None

    def __init__(self, conn, matching_row):
        self.matching_row = matching_row
        self.conn = conn

    @abstractmethod
    def modify_bubble(self) -> List[SendingInfo]:
        pass

    def _change_state(self):
        change_state(self.conn, self.old_state,
                     self.new_state, self.matching_row.id)

    def send(self, change_state):
        sending_infos = self.modify_bubble()
        for recipient, bubble, alt in sending_infos:
            send_bubble_to_member_id(
                self.conn, recipient, bubble, alt_text=alt)

        if change_state:
            if self.NOTIFICATION:
                raise ValueError("A Notification can not change state.")
            else:
                self._change_state()


class InvitationSender(Sender):
    OLD_STATE = 'invitation_sending'
    NEW_STATE = 'invitation_waiting'

    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/invitation'
        intro_link = get_introduction_link(
            self.conn, self.matching_row.object_id)
        name = get_proper_name(self.conn, self.matching_row.object_id)
        bubble = set_basic_bubble(
            bubble, '約會邀請卡', self.matching_row.city, name, intro_link, form_app_link, '開啟邀請卡')

        return [SendingInfo(self.matching_row.subject_id, bubble, '🎉接收您的約會邀請卡')]


class LikedSender(Sender):
    OLD_STATE = 'liked_sending'
    NEW_STATE = 'liked_waiting'

    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/liked'
        intro_link = get_introduction_link(
            self.conn, self.matching_row.subject_id)
        name = get_proper_name(self.conn, self.matching_row.subject_id)
        bubble = set_basic_bubble(
            bubble, '約會邀請卡', self.matching_row.city, name, intro_link, form_app_link, '開啟邀請卡')

        return [SendingInfo(self.matching_row.object_id, bubble, '🎉開啟您的約會邀請卡')]


class GoodbyeSender(Sender):
    OLD_STATE = 'goodbye_sending'
    NEW_STATE = 'goodbye'

    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)

        message = "此約會邀請依雙方意願時間暫不安排\n期待未來比次更多的緣分"
        alt_message = '後會有期🥲期待新的約會邀請'

        bubble_for_obj, bubble_for_sub = set_two_way_bubble_link_intro(
            self.conn, bubble, self.matching_row, message, '後會有期！')

        return [SendingInfo(
            self.matching_row.object_id, bubble_for_obj, alt_message),
            SendingInfo(
            self.matching_row.subject_id, bubble_for_sub, alt_message)]


class RestR1Sender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r1'

        send_to_id = get_gender_id(self.conn, self.matching_row, 'F')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'M')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)
        message = '請提供心儀之約會餐廳與時間'
        bubble = set_basic_bubble(
            bubble, '此約會邀請成功', self.matching_row.city, name,
            intro_link, form_app_link, '開啟約會資訊卡', message)

        return [SendingInfo(send_to_id, bubble, alt='選餐廳囉～')]


class RestR2Sender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r2'

        send_to_id = get_gender_id(self.conn, self.matching_row, 'M')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'F')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)
        message = '請您提供可配合時間與餐廳訂位\n若需進一步溝通請於資訊卡留言'
        bubble = set_basic_bubble(
            bubble, '此約會邀請成功', self.matching_row.city,
            name, intro_link, form_app_link, '開啟資訊卡', message)

        return [SendingInfo(send_to_id, bubble, alt='來囉！開啟此趟約會行程確認')]


class RestR3Sender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r3'

        send_to_id = get_gender_id(self.conn, self.matching_row, 'F')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'M')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)
        message = '男生已確認要約並想與妳開啟約會內容溝通\n請您進一步開啟溝通卡內容'
        bubble = set_basic_bubble(
            bubble, '約會資訊溝通卡', self.matching_row.city, name,
            intro_link, form_app_link, '開啟溝通卡', message)

        return [SendingInfo(send_to_id, bubble, alt='開啟您的約會資訊溝通卡')]


class RestR4Sender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r4'

        send_to_id = get_gender_id(self.conn, self.matching_row, 'M')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'F')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)
        message = '請您提供可配合時間與餐廳訂位\n若需進一步溝通請於資訊卡留言'
        bubble = set_basic_bubble(
            bubble, '此約會溝通成功', self.matching_row.city, name, intro_link,
            form_app_link, '開啟溝通卡', message)

        return [SendingInfo(send_to_id, bubble, alt='恭喜溝通成功')]


class DealSender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)

        message = "牽線成功\n收到此出擊提醒請務必點擊下方確認扭\n讓我們知道你已收到這個好消息！"
        alt_message = '開啟您的約會出席提醒'

        bubble_for_obj, bubble_for_sub = set_two_way_bubble_link_intro(
            self.conn, bubble, self.matching_row, message, '約會出席提醒')

        return [SendingInfo(
            self.matching_row.object_id, bubble_for_obj, alt_message),
            SendingInfo(
            self.matching_row.subject_id, bubble_for_sub, alt_message)]


class NotificationSender(Sender):
    # 約會前通知
    def modify_bubble(self):
        return super().modify_bubble()


class CancelNotifySender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)

        sending_infos = []

        # 上面要有：改期連結（帶有他的id）、對方的名字、對方的介紹頁、(訂位大名、訂位聯絡、訂位留言、城市、餐廳連結)
        obj_form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/cancel'
        obj_intro_link = get_introduction_link(
            self.conn, self.matching_row.object_id)
        obj_name = get_proper_name(self.conn, self.matching_row.object_id)

        bubble = set_deal_bubble(
            bubble, '餐廳確認資訊', self.matching_row.city, name, intro_link, form_app_link, '選擇最終餐廳')

        return [SendingInfo(self.matching_row.object_id, bubble_for_obj),
                SendingInfo(self.matching_row.subject_id, bubble_for_sub)]


class Invitation24Sender(Sender):
    OLD_STATE = 'invitation24_sending'
    NEW_STATE = 'invitation24_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class Invitation48Sender(Sender):
    OLD_STATE = 'invitation48_sending'
    NEW_STATE = 'invitation48_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class Liked24Sender(Sender):
    OLD_STATE = 'liked24_sending'
    NEW_STATE = 'liked24_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class Liked48Sender(Sender):
    OLD_STATE = 'liked48_sending'
    NEW_STATE = 'liked48_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR124Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR148Sender(Sender):
    OLD_STATE = 'rest_r148_sending'
    NEW_STATE = 'rest_r148_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR224Sender(Sender):
    OLD_STATE = 'rest_r224_sending'
    NEW_STATE = 'rest_r224_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR248Sender(Sender):
    OLD_STATE = 'rest_r248_sending'
    NEW_STATE = 'rest_r248_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR324Sender(Sender):
    OLD_STATE = 'rest_r324_sending'
    NEW_STATE = 'rest_r324_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR348Sender(Sender):
    OLD_STATE = 'rest_r348_sending'
    NEW_STATE = 'rest_r348_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR424Sender(Sender):
    OLD_STATE = 'rest_r424_sending'
    NEW_STATE = 'rest_r424_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR448Sender(Sender):
    OLD_STATE = 'rest_r448_sending'
    NEW_STATE = 'rest_r448_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class NoActionGoodbyeSender(Sender):
    OLD_STATE = 'no_action_goodbye_sending'
    NEW_STATE = 'goodbye'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class Deal1DDealSender(Sender):
    OLD_STATE = 'deal_1d_notification_sending'
    NEW_STATE = 'deal_1d_notification_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class Deal3HRSender(Sender):
    OLD_STATE = 'deal_3hr_notification_sending'
    NEW_STATE = 'deal_3hr_notification_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class SuddenChangeTimeSender(Sender):
    OLD_STATE = 'sudden_change_time_notification_sending'
    NEW_STATE = 'sudden_change_time_notification_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class NextMonthSender(Sender):
    OLD_STATE = 'next_month_sending'
    NEW_STATE = 'next_month_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class ChangeTimeSender(Sender):
    OLD_STATE = 'change_time_sending'
    NEW_STATE = 'change_time_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class RestR1NextMonthSender(Sender):
    OLD_STATE = 'rest_r1_next_month_sending'
    NEW_STATE = 'rest_r1_next_month_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class DatingNotificationSender(Sender):
    OLD_STATE = 'dating_notification_sending'
    NEW_STATE = 'dating_notification_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


class DatingFeedbackSender(Sender):
    OLD_STATE = 'dating_feedback_sending'
    NEW_STATE = 'dating_feedback_waiting'

    def modify_bubble(self):
        # TODO: Implement actual bubble logic
        return []


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
