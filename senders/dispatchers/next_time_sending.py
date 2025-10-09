
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
        current_state = %s;
        """
        with self.conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('next_time_sending',)).fetchall()


class MySender(Sender):
    OLD_STATE = 'next_time_sending'
    NEW_STATE = 'rest_r1_next_month_sending'

    def modify_bubble(self):
        def message_factory(member_id):
            message = f"""代表城市：{self.matching_row.city}\n
            因時間上的問題，與{get_proper_name(self.conn, member_id)}的約會將延後安排
            """
            return message

        message_for_obj = message_factory(self.matching_row.subject_id)
        message_for_sub = message_factory(self.matching_row.object_id)

        return [SendingInfo(
            self.matching_row.object_id, message_for_obj, alt=""),
            SendingInfo(
            self.matching_row.subject_id, message_for_sub, alt="")]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
