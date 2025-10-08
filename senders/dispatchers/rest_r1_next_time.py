
import psycopg
from base import Collector, Dispatcher, Sender, SendingInfo
from config import DB, FORM_WEB_URL
from psycopg.rows import namedtuple_row
from senders_utils import (get_gender_id, get_introduction_link,
                           get_proper_name, load_bubble_raw)


class MyCollector(Collector):
    def collect(self):
        stmt = """
        select * from
        matching where
        current_state = %s
        and now() - last_sent_at > interval '14 days' ;
        """
        with self.conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('rest_r1_next_month_sending',)).fetchall()


class MySender(Sender):
    OLD_STATE = 'rest_r1_next_time_sending'
    NEW_STATE = 'rest_r1_waiting'

    def modify_bubble(self):
        bubble = load_bubble_raw('basic_bubble.json')

        bubble.set_title('約會邀請卡')
        bubble.set_city(self.matching_row.city)
        form_app_link = f'{FORM_WEB_URL}/{self.matching_row.access_token}/rest_r1'
        bubble.set_form_app_link(form_app_link)
        send_to_id = get_gender_id(self.conn, self.matching_row, 'F')
        rendered_id = get_gender_id(self.conn, self.matching_row, 'M')

        intro_link = get_introduction_link(self.conn, rendered_id)
        name = get_proper_name(self.conn, rendered_id)

        bubble.set_intro_link(intro_link)
        bubble.set_sent_to_proper_name(name)

        message = '請提供心儀之約會餐廳與時間'

        bubble.set_bubble_message(message)

        return [SendingInfo(send_to_id, bubble.as_dict(), alt='來囉！開啟此趟約會行程確認')]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
