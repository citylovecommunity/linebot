
import psycopg
from base import Collector, Dispatcher, Sender, SendingInfo
from collector_utils import get_list
from config import DB, FORM_WEB_URL
from senders_utils import (get_introduction_link, get_proper_name,
                           load_bubble_raw, show_google_map_name)


class MyCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'deal')


class MySender(Sender):
    OLD_STATE = 'deal_sending'
    NEW_STATE = 'deal_1d_notification_sending'

    def modify_bubble(self):
        base_bubble = load_bubble_raw('deal_bubble.json')

        alt_message = '開啟您的約會出席提醒'
        # 先把一些共同有的置換上去
        base_bubble.set_title('約會出席提醒')
        base_bubble.set_city(self.matching_row.city)
        base_bubble.set_date(
            self.matching_row.selected_date.strftime('%Y-%m-%d'))
        base_bubble.set_time(
            self.matching_row.book_time.strftime('%H:%M'))

        base_bubble.set_book_name(self.matching_row.book_name)
        # base_bubble.set_book_phone(self.matching_row.book_phone)
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


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
