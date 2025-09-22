
import psycopg
from base import Collector, Dispatcher, Sender, SendingInfo
from config import DB
from psycopg.rows import namedtuple_row
from senders_utils import get_proper_name, get_phone_number


class MyCollector(Collector):
    def collect(self):
        stmt = """
        select * from
        matching where
        current_state = %s
        and selected_time - now() < interval '3 hour' ;
        """
        with conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('deal_3hr_notification_sending',)).fetchall()


class MySender(Sender):
    OLD_STATE = 'deal_3hr_notification_sending'
    NEW_STATE = 'dating_notification_sending'

    def modify_bubble(self):
        message_for_obj = f"""
        提醒您再3小時後即將與{get_proper_name(self.conn, self.matching_row.subject_id)}約會\n
        這是對方的電話號碼：{get_phone_number(self.conn, self.matching_row.subject_id)}\n
        若有任何問題，請直接與對方聯繫。\n
        祝您約會愉快！
        """
        message_for_sub = f"""
        提醒您再3小時後即將與{get_proper_name(self.conn, self.matching_row.object_id)}約會\n
        這是對方的電話號碼：{get_phone_number(self.conn, self.matching_row.object_id)}\n
        若有任何問題，請直接與對方聯繫。\n
        祝您約會愉快！
        """

        return [SendingInfo(
            self.matching_row.object_id, message_for_obj, alt=""),
            SendingInfo(
            self.matching_row.subject_id, message_for_sub, alt="")]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
