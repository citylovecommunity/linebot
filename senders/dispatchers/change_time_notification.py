
import psycopg
from base import Collector, Dispatcher, Sender, SendingInfo
from config import DB
from psycopg.rows import namedtuple_row
from senders_utils import get_proper_name


class MyCollector(Collector):
    def collect(self):
        stmt = """
        select * from
        matching where
        current_state = %s
        """
        with self.conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('change_time_notification',)).fetchall()


class MySender(Sender):
    OLD_STATE = 'change_time_notification'
    NEW_STATE = 'rest_r1_next_time_sending'

    def modify_bubble(self):
        def message_factory(member_id):
            message = f"""代表城市：{self.matching_row.city}\n因某一方臨時有事，與{get_proper_name(self.conn, member_id)}的約會將延後安排
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
