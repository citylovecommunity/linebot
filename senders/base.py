from abc import ABC, abstractmethod
from collections import namedtuple
from typing import List, NamedTuple

import psycopg
from config import SENDER_PRODUCTION
from senders_utils import (change_state, send_bubble_to_member_id,
                           send_normal_text, write_sent_to_db)


class Collector(ABC):
    """
    負責決定哪些配對是本次傳送的對象
    """

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    @abstractmethod
    def collect(self) -> list[NamedTuple]:
        pass


SendingInfo = namedtuple('SendingInfo', ['recipient', 'bubble', 'alt'])


class Sender(ABC):
    OLD_STATE = None
    NEW_STATE = None
    NOTIFICATION = None

    def __init__(self, conn, matching_row):
        self.matching_row = matching_row
        self.conn = conn

    @abstractmethod
    def modify_bubble(self) -> List[SendingInfo]:
        pass

    def _change_state(self):
        change_state(self.conn, self.OLD_STATE,
                     self.NEW_STATE, self.matching_row.id)

    def send(self):
        sending_infos = self.modify_bubble()
        for recipient, body, alt in sending_infos:

            if isinstance(body, str):
                real_sending_info = send_normal_text(
                    self.conn, recipient, body)
            else:
                real_sending_info = send_bubble_to_member_id(
                    self.conn, recipient, body, alt_text=alt)
            write_sent_to_db(self.conn, self.matching_row.id,
                             real_sending_info.body,
                             real_sending_info.send_to)

        if not self.NOTIFICATION:
            self._change_state()


class Dispatcher:
    def __init__(self, conn: psycopg.Connection, collector: Collector, sender: Sender):
        self.conn = conn
        self.collector = collector(conn)
        self.sender = sender

        self._users = self.collector.collect()

    def show_collection(self):
        return self._users

    def send(self):
        if len(self._users) > 0:
            if SENDER_PRODUCTION:
                for matching_row in self._users:
                    self.sender(self.conn, matching_row).send(change_state)
            else:
                self.sender(self.conn, self._users[0]).send(change_state)
