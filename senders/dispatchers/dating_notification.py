
import psycopg
from base import Collector, Dispatcher, Sender, SendingInfo
from config import DB
from psycopg.rows import namedtuple_row


class MyCollector(Collector):
    def collect(self):
        stmt = """
        select * from
        matching where
        current_state = %s
        and selected_time - now() < interval '1 day' ;
        """
        with conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('deal_1d_notification_sending',)).fetchall()


class MySender(Sender):
    OLD_STATE = 'deal_1d_notification_sending'
    NEW_STATE = 'deal_3hr_notification_sending'

    def modify_bubble(self):
        message = """📅 溫馨提醒：明天您有一場約會 😊
        📌 請務必準時抵達，建議您提早 5～10 分鐘到場，避免讓對方久等唷 🙇
        """

        return [SendingInfo(
            self.matching_row.object_id, message, alt=""),
            SendingInfo(
            self.matching_row.subject_id, message, alt="")]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
