import psycopg
from base import Collector, Dispatcher, Sender, SendingInfo
from config import DB, FORM_WEB_URL
from psycopg.rows import namedtuple_row
from senders_utils import (get_introduction_link, get_proper_name,
                           load_bubble_raw)


class MyCollector(Collector):
    def collect(self):
        stmt = """
        select * from
        matching where
        current_state = %s;
        """
        with self.conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('invitation_sending',)).fetchall()


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
