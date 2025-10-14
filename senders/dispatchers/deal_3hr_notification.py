
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
        and current_date = selected_date 
        and book_time - (current_time AT TIME ZONE 'Asia/Taipei')::time < interval '3 hour' ;
        """
        with self.conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('deal_3hr_notification_sending',)).fetchall()


class MySender(Sender):
    OLD_STATE = 'deal_3hr_notification_sending'
    NEW_STATE = 'dating_feedback_sending'

    def modify_bubble(self):
        def message_format(name, number):
            message = f"""提醒您再3小時後即將與{name}約會\n\n這是對方的電話號碼：{number}\n\n若有任何問題，請別害羞直接與對方聯繫。\n\n祝您約會愉快！"""
            return message

        message_for_obj = message_format(get_proper_name(
            self.conn, self.matching_row.subject_id), get_phone_number(self.conn, self.matching_row.subject_id))

        message_for_sub = message_format(get_proper_name(
            self.conn, self.matching_row.object_id), get_phone_number(self.conn, self.matching_row.object_id))

        return [SendingInfo(
            self.matching_row.object_id, message_for_obj, alt=""),
            SendingInfo(
            self.matching_row.subject_id, message_for_sub, alt="")]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
