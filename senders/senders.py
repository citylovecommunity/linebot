
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import List

from config import FORM_WEB_URL
from senders_utils import (change_state, get_gender_id, get_introduction_link,
                           get_proper_name, load_bubble, load_bubble_raw,
                           send_bubble_to_member_id, send_normal_text,
                           show_google_map_name, write_sent_to_db)

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
        change_state(self.conn, self.OLD_STATE,
                     self.NEW_STATE, self.matching_row.id)

    def send(self, change_state):
        sending_infos = self.modify_bubble()
        for recipient, body, alt in sending_infos:
            if self.NOTIFICATION:
                real_sending_info = send_normal_text(
                    self.conn, recipient, body)
            else:
                real_sending_info = send_bubble_to_member_id(
                    self.conn, recipient, body, alt_text=alt)
            write_sent_to_db(self.conn, self.matching_row.id,
                             real_sending_info.body,
                             real_sending_info.send_to)

        if change_state and not self.NOTIFICATION:
            self._change_state()


class InvitationSender(Sender):
    OLD_STATE = 'invitation_sending'
    NEW_STATE = 'invitation_waiting'

    def modify_bubble(self):
        bubble = load_bubble_raw('basic_bubble.json')

        bubble.set_title('約會邀請卡')

        bubble.set_city(self.matching_row.city)
        bubble.set_form_app_link(
            f'{FORM_WEB_URL}/{self.matching_row.access_token}/invitation')

        bubble.set_intro_link(get_introduction_link(
            self.conn, self.matching_row.object_id))
        bubble.set_sent_to_proper_name(get_proper_name(
            self.conn, self.matching_row.object_id))

        return [SendingInfo(self.matching_row.subject_id, bubble.as_dict(), '🎉接收您的約會邀請卡')]


class Invitation24Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class Invitation48Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class LikedSender(Sender):
    OLD_STATE = 'liked_sending'
    NEW_STATE = 'liked_waiting'

    def modify_bubble(self):
        bubble = load_bubble_raw('basic_bubble.json')

        bubble.set_title('約會邀請卡')
        bubble.set_city(self.matching_row.city)
        bubble.set_form_app_link(
            f'{FORM_WEB_URL}/{self.matching_row.access_token}/liked')

        bubble.set_intro_link(get_introduction_link(
            self.conn, self.matching_row.subject_id))
        bubble.set_sent_to_proper_name(get_proper_name(
            self.conn, self.matching_row.subject_id))
        return [SendingInfo(self.matching_row.object_id, bubble.as_dict(), '🎉開啟您的約會邀請卡')]


class Liked24Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class Liked48Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class RestR124Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class RestR148Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class RestR224Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class RestR248Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class RestR324Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class RestR348Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class RestR424Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


class RestR448Sender(Sender):
    NOTIFICATION = True

    def modify_bubble(self):
        return [SendingInfo(self.matching_row.subject_id, '你好，請趕快點開你的東西', '通知通知～')]


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
    OLD_STATE = 'rest_r1_sending'
    NEW_STATE = 'rest_r1_waiting'

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

        return [SendingInfo(send_to_id, bubble, alt='來囉！開啟此趟約會行程確認')]


class RestR2Sender(Sender):
    OLD_STATE = 'rest_r2_sending'
    NEW_STATE = 'rest_r2_waiting'

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
    OLD_STATE = 'deal_sending'
    NEW_STATE = 'deal_1d_notification_sending'

    def modify_bubble(self):
        base_bubble = load_bubble_raw('deal_bubble.json')

        alt_message = '開啟您的約會出席提醒'
        # 先把一些共同有的置換上去

        base_bubble.set_city(self.matching_row.city)
        base_bubble.set_time(
            self.matching_row.selected_time.strftime('%Y-%m-%d %H:%M'))
        base_bubble.set_book_name(self.matching_row.book_name)
        base_bubble.set_book_phone(self.matching_row.book_phone)
        base_bubble.set_message(self.matching_row.comment)
        base_bubble.set_rest_url(self.matching_row.selected_place)
        base_bubble.set_rest_name(show_google_map_name(
            self.matching_row.selected_place))

        # 不同的
        bubble_for_sub = base_bubble.copy()
        bubble_for_obj = base_bubble.copy()

        # 稱謂
        bubble_for_sub.set_sent_to_proper_name(
            get_proper_name(self.conn, self.matching_row.object_id))
        bubble_for_obj.set_sent_to_proper_name(
            get_proper_name(self.conn, self.matching_row.subject_id))

        # 介紹卡連結
        bubble_for_sub.set_intro_link(
            get_introduction_link(self.conn, self.matching_row.object_id))
        bubble_for_obj.set_intro_link(
            get_introduction_link(self.conn, self.matching_row.subject_id))

        # 改期連結
        change_time_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/change_time/'
        bubble_for_sub.set_form_app_link(change_time_link+'sub')
        bubble_for_obj.set_form_app_link(change_time_link+'obj')

        return [SendingInfo(
            self.matching_row.object_id, bubble_for_obj.as_dict(), alt_message),
            SendingInfo(
            self.matching_row.subject_id, bubble_for_sub.as_dict(), alt_message)]


class NoActionGoodbyeSender(Sender):
    OLD_STATE = 'no_action_goodbye_sending'
    NEW_STATE = 'goodbye'

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


class Deal1DDealSender(Sender):
    OLD_STATE = 'deal_1d_notification_sending'
    NEW_STATE = 'deal_3hr_notification_sending'

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


class Deal3HRSender(Sender):
    OLD_STATE = 'deal_3hr_notification_sending'
    NEW_STATE = 'dating_notification_sending'

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


class SuddenChangeTimeSender(Sender):
    OLD_STATE = 'sudden_change_time_notification_sending'
    NEW_STATE = 'change_time_sending'

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


class NextMonthSender(Sender):
    OLD_STATE = 'next_month_sending'
    NEW_STATE = 'next_month_waiting'

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


class ChangeTimeSender(Sender):
    OLD_STATE = 'change_time_sending'
    NEW_STATE = 'rest_r1_waiting'

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


class RestR1NextMonthSender(Sender):
    OLD_STATE = 'rest_r1_next_month_sending'
    NEW_STATE = 'rest_r1_next_month_waiting'

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


class DatingNotificationSender(Sender):
    OLD_STATE = 'dating_notification_sending'
    NEW_STATE = 'dating_notification_waiting'

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


class DatingFeedbackSender(Sender):
    OLD_STATE = 'dating_feedback_sending'
    NEW_STATE = 'dating_done'

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
