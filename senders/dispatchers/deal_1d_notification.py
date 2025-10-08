
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
        and selected_date - current_date < 2 ;
        """
        with self.conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('deal_1d_notification_sending',)).fetchall()


class MySender(Sender):
    OLD_STATE = 'deal_1d_notification_sending'
    NEW_STATE = 'deal_3hr_notification_sending'

    def modify_bubble(self):
        def message_factory(member_id):
            message = f"""代表城市：{self.matching_row.city}\n
            📅 溫馨提醒：明天您有一場與{get_proper_name(member_id)}的約會 😊\n📌 請務必準時抵達，建議您提早 5～10 分鐘到場，避免讓對方久等唷 🙇
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
