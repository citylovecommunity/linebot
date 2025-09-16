import psycopg
from config import FORM_WEB_URL, DB
from senders_utils import load_bubble_raw, get_proper_name, get_introduction_link
from base import Collector, Sender, SendingInfo, Dispatcher
from psycopg.rows import namedtuple_row


class MyCollector(Collector):
    """
    liked，但是如果obj_id有超過3個正在約會中的state，就不要
    """

    def collect(self):
        stmt = """
        select * from
        matching where
        current_state = %s
        and object_id not in (
            select object_id
            from matching
            where current_state not in ('invitation_sending', 'goodbye')
            group by object_id
            having count(*) >= 3
            );
        """
        with self.conn.cursor(row_factory=namedtuple_row) as cur:
            return cur.execute(stmt, ('liked_sending',)).fetchall()


class MySender(Sender):
    OLD_STATE = 'liked_sending'
    NEW_STATE = 'liked_waiting'

    def modify_bubble(self):
        bubble = load_bubble_raw('basic_bubble.json')

        bubble.set_title('約會邀請卡')
        bubble.set_city(self.matching_row.city)
        bubble.set_form_app_link(
            f'{FORM_WEB_URL}/{self.matching_row.access_token}/liked')
        bubble.set_bubble_message("這是一個約會邀請卡")
        bubble.set_intro_link(get_introduction_link(
            self.conn, self.matching_row.subject_id))
        bubble.set_sent_to_proper_name(get_proper_name(
            self.conn, self.matching_row.subject_id))
        return [SendingInfo(self.matching_row.object_id, bubble.as_dict(), '🎉開啟您的約會邀請卡')]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
