from abc import ABC, abstractmethod

import psycopg
from psycopg.rows import namedtuple_row
from typing import NamedTuple


def get_list(conn, state):
    stmt = """
    select * from
    matching where
    current_state = %s;
    """
    with conn.cursor(row_factory=namedtuple_row) as cur:
        return cur.execute(stmt, (state+'_sending',)).fetchall()


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
        and obj_id not in (
            select obj_id
            from matching
            where current_state not in ('invitation', 'goodbye')
            group by obj_id
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
