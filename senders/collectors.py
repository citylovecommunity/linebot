from abc import ABC, abstractmethod
from typing import NamedTuple

import psycopg
from psycopg.rows import namedtuple_row


def get_list(conn, state):
    stmt = """
    select * from
    matching where
    current_state = %s;
    """
    with conn.cursor(row_factory=namedtuple_row) as cur:
        return cur.execute(stmt, (state+'_sending',)).fetchall()


def get_notification_list(conn, state, time):
    if time == '24':
        stmt = """
        select * from
        matching where
        current_state = %s
        and now() - last_sent_at between interval '24 hours' and interval '48 hours'
        ;
        """
    elif time == '48':
        stmt = """
        select * from
        matching where
        current_state = %s
        and now() - last_sent_at >= interval '48 hours'
        """
    else:
        raise ValueError('time must be 24 or 48')
    with conn.cursor(row_factory=namedtuple_row) as cur:
        return cur.execute(stmt, (state+'_waiting',)).fetchall()


class Collector(ABC):
    """
    負責決定哪些配對是本次傳送的對象
    """

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    @abstractmethod
    def collect(self) -> list[NamedTuple]:
        pass


class InvitationCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'invitation')


class LikedCollector(Collector):
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


class RestR1Collector(Collector):
    def collect(self):
        return get_list(self.conn, 'rest_r1')


class RestR2Collector(Collector):
    def collect(self):
        return get_list(self.conn, 'rest_r2')


class RestR3Collector(Collector):
    def collect(self):
        return get_list(self.conn, 'rest_r3')


class RestR4Collector(Collector):
    def collect(self):
        return get_list(self.conn, 'rest_r4')


class GoodbyeCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'goodbye')


class DealCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'deal')


class ChangeTimeCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'change_time')


class Invitation24Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'invitation', '24')


class Invitation48Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'invitation', '48')


class Liked24Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'liked', '24')


class Liked48Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'liked', '48')


class RestR124Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'rest_r1', '24')


class RestR148Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'rest_r1', '48')


class RestR224Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'rest_r2', '24')


class RestR248Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'rest_r2', '48')


class RestR324Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'rest_r3', '24')


class RestR348Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'rest_r3', '48')


class RestR424Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'rest_r4', '24')


class RestR448Collector(Collector):
    def collect(self):
        return get_notification_list(self.conn, 'rest_r4', '48')


class NoActionGoodbyeCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'no_action_goodbye_sending')


class Deal1DCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'deal_1d_notification_sending')


class Deal3HRCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'deal_3hr_notification_sending')


class SuddenChangeTimeCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'sudden_change_time_notification_sending')


class NextMonthCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'next_month_waiting')


class ChangeTimeCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'change_time_sending')


class RestR1NextMonthCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'rest_r1_next_month_sending')


class DatingNotificationCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'dating_notification_sending')


class DatingFeedbackCollector(Collector):
    def collect(self):
        return get_list(self.conn, 'dating_feedback_sending')
