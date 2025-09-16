
import psycopg
from config import FORM_WEB_URL, DB
from senders_utils import load_bubble_raw, get_proper_name, get_introduction_link, get_gender_id
from collector_utils import get_list
from base import Collector, Sender, SendingInfo, Dispatcher


class MyCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'rest_r3')


class MySender(Sender):
    def modify_bubble(self):

        bubble = load_bubble_raw('basic_bubble.json')

        bubble.set_title('約會邀請卡')
        bubble.set_city(self.matching_row.city)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r3'
        bubble.set_form_app_link(form_app_link)
        send_to_id = get_gender_id(self.conn, self.matching_row, 'F')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'M')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)

        bubble.set_intro_link(intro_link)
        bubble.set_sent_to_proper_name(name)

        message = '男生已確認要約並想與妳開啟約會內容溝通\n請您進一步開啟溝通卡內容'

        bubble.set_bubble_message(message)

        return [SendingInfo(send_to_id, bubble.as_dict(), alt='開啟您的約會資訊溝通卡')]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
