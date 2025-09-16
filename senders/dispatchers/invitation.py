import psycopg
from config import FORM_WEB_URL, DB
from senders_utils import load_bubble_raw, get_proper_name, get_introduction_link
from collector_utils import get_list
from base import Collector, Sender, SendingInfo, Dispatcher


class MyCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'invitation')


class MySender(Sender):
    OLD_STATE = 'invitation_sending'
    NEW_STATE = 'invitation_waiting'

    def modify_bubble(self):
        bubble = load_bubble_raw('basic_bubble.json')

        bubble.set_title('約會邀請卡')

        bubble.set_bubble_message("這是一個約會邀請卡")
        bubble.set_city(self.matching_row.city)
        bubble.set_form_app_link(
            f'{FORM_WEB_URL}/{self.matching_row.access_token}/invitation')

        bubble.set_intro_link(get_introduction_link(
            self.conn, self.matching_row.object_id))
        bubble.set_sent_to_proper_name(get_proper_name(
            self.conn, self.matching_row.object_id))

        return [SendingInfo(self.matching_row.subject_id, bubble.as_dict(), '🎉接收您的約會邀請卡')]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
