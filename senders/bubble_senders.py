from abc import ABC, abstractmethod
from collections import namedtuple
from typing import List

from config import BUBBLE_HERO_IMAGE_URL, FORM_WEB_URL
from senders_utils import (get_gender_id, get_introduction_link,
                           get_proper_name, load_bubble, send_bubble_to_member_id)


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


def set_basic_bubble(bubble, title, city, name, intro_link, form_link, form_label):
    bubble = set_basic_bubble_title(bubble, title)
    bubble = set_basic_bubble_city(bubble, city)
    bubble = set_basic_bubble_name(bubble, name)
    bubble = set_basic_bubble_intro_link(bubble, intro_link)
    bubble = set_basic_bubble_form_link(
        bubble, form_link, form_label)
    return bubble


SendingInfo = namedtuple('SendingInfo', ['recipient', 'bubble'])


class Sender(ABC):
    def __init__(self, conn, matching_row):
        self.matching_row = matching_row
        self.conn = conn

    @abstractmethod
    def modify_bubble(self) -> List[SendingInfo]:
        pass

    def send(self):
        sending_infos = self.modify_bubble()
        for recipient, bubble in sending_infos:
            send_bubble_to_member_id(self.conn, recipient, bubble)


class InvitationSender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/invitation'
        intro_link = get_introduction_link(
            self.conn, self.matching_row.object_id)
        name = get_proper_name(self.conn, self.matching_row.object_id)
        bubble = set_basic_bubble(
            bubble, '約會邀請卡', self.matching_row.city, name, intro_link, form_app_link, '開啟邀請卡')

        return [SendingInfo(self.matching_row.subject_id, bubble)]


class LikedSender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/liked'
        intro_link = get_introduction_link(
            self.conn, self.matching_row.subject_id)
        name = get_proper_name(self.conn, self.matching_row.subject_id)
        bubble = set_basic_bubble(
            bubble, '約會回覆卡', self.matching_row.city, name, intro_link, form_app_link, '開啟回覆卡')

        return [SendingInfo(self.matching_row.object_id, bubble)]


class RestR1Sender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r1'

        send_to_id = get_gender_id(self.conn, self.matching_row, 'F')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'M')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)
        bubble = set_basic_bubble(
            bubble, '餐廳選擇卡', self.matching_row.city, name, intro_link, form_app_link, '選擇餐廳')

        return [SendingInfo(send_to_id, bubble)]


class RestR2Sender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r2'

        send_to_id = get_gender_id(self.conn, self.matching_row, 'M')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'F')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)
        bubble = set_basic_bubble(
            bubble, '餐廳訂位卡', self.matching_row.city, name, intro_link, form_app_link, '餐廳訂位')

        return [SendingInfo(send_to_id, bubble)]


class RestR3Sender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r3'

        send_to_id = get_gender_id(self.conn, self.matching_row, 'F')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'M')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)
        bubble = set_basic_bubble(
            bubble, '餐廳時間重選卡', self.matching_row.city, name, intro_link, form_app_link, '重選餐廳時間')

        return [SendingInfo(send_to_id, bubble)]


class RestR4Sender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('basic_bubble.json')
        bubble = base_modifier(base_bubble)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r4'

        send_to_id = get_gender_id(self.conn, self.matching_row, 'M')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'F')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)
        bubble = set_basic_bubble(
            bubble, '餐廳最終訂位卡', self.matching_row.city, name, intro_link, form_app_link, '選擇最終餐廳')

        return [SendingInfo(send_to_id, bubble)]


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


class DealSender(Sender):
    def modify_bubble(self):
        base_bubble = load_bubble('deal_bubble')
        bubble = base_modifier(base_bubble)

        # Common Fields
        city = self.matching_row.city
        rest_link = self.matching_row.selected_place
        time = self.matching_row.selected_time
        phone = self.matching_row.book_phone
        message = self.matching_row.comment
        rest_name = self.matching_row.book_name

        # obj
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/cancel'
        intro_link = get_introduction_link(
            self.conn, self.matching_row.subject_id)
        name = get_proper_name(self.conn, self.matching_row.subject_id)

        bubble_for_obj = set_deal_bubble(
            bubble, city, name, rest_name, phone, message, time, rest_link, intro_link, form_app_link)

        obj_sending_info = SendingInfo(
            self.matching_row.object_id, bubble_for_obj)

        # sub
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/cancel'
        intro_link = get_introduction_link(
            self.conn, self.matching_row.object_id)
        name = get_proper_name(self.conn, self.matching_row.object_id)

        bubble = set_deal_bubble(
            bubble, city, name, rest_name, phone, message, time, rest_link, intro_link, form_app_link)

        sub_sending_info = SendingInfo(
            self.matching_row.object_id, bubble_for_obj)

        return [obj_sending_info, sub_sending_info]


class NotificationSender(Sender):
    # 約會前通知
    def modify_bubble(self):
        return super().modify_bubble()


class WasteSender(Sender):
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
