
import psycopg
from base import Collector, Dispatcher, Sender, SendingInfo
from collector_utils import get_list
from config import DB
from senders_utils import get_proper_name, load_bubble_raw


class MyCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'deal')


class MySender(Sender):
    OLD_STATE = ('goodbye_sending', 'no_action_goodbye_sending')
    NEW_STATE = 'goodbye'

    def modify_bubble(self):
        bubble = load_bubble_raw('simple_message_bubble.json')
        message = "此約會邀請依雙方意願時間暫不安排\n期待未來比次更多的緣分"

        bubble.set_title('後會有期！')
        bubble.set_city(self.matching_row.city)
        bubble.set_bubble_message(message)

        bubble_for_obj = bubble.copy()
        bubble_for_sub = bubble.copy()

        bubble_for_obj.set_sent_to_proper_name(get_proper_name(
            self.conn, self.matching_row.subject_id))
        bubble_for_sub.set_sent_to_proper_name(get_proper_name(
            self.conn, self.matching_row.object_id))

        alt_message = '後會有期🥲期待新的約會邀請'

        return [SendingInfo(
            self.matching_row.object_id, bubble_for_obj.as_dict(), alt_message),
            SendingInfo(
            self.matching_row.subject_id, bubble_for_sub.as_dict(), alt_message)]


if __name__ == '__main__':
    with psycopg.connect(DB) as conn:
        dispatcher = Dispatcher(conn, MyCollector, MySender)
        dispatcher.send()
