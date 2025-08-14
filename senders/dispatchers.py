import random

import psycopg
from collectors import (Collector, DealCollector, GoodbyeCollector,
                        InvitationCollector, LikedCollector, RestR1Collector,
                        RestR2Collector, RestR3Collector, RestR4Collector)

from senders import (DealSender, GoodbyeSender, InvitationSender, LikedSender,
                     RestR1Sender, RestR2Sender, RestR3Sender, RestR4Sender,
                     Sender)


class Dispatcher:
    def __init__(self, conn: psycopg.Connection, collector: Collector, sender: Sender):
        self.conn = conn
        self.collector = collector(conn)
        self.sender = sender

        self._users = self.collector.collect()

    def show_collection(self):
        return self._users

    def send_all(self):
        for matching_row in self._users:
            self.sender(self.conn, matching_row).send()

    def send_one(self):
        self.sender(self.conn, random.choice(self._users)).send()


class InvitationDispatcher(Dispatcher):
    def __init__(self, conn):
        super().__init__(conn, InvitationCollector, InvitationSender)


class LikedDispatcher(Dispatcher):
    def __init__(self, conn):
        super().__init__(conn, LikedCollector, LikedSender)


class GoodbyeDispatcher(Dispatcher):
    def __init__(self, conn):
        super().__init__(conn, GoodbyeCollector, GoodbyeSender)


class RestR1Dispatcher(Dispatcher):
    def __init__(self, conn):
        super().__init__(conn, RestR1Collector, RestR1Sender)


class RestR2Dispatcher(Dispatcher):
    def __init__(self, conn):
        super().__init__(conn, RestR2Collector, RestR2Sender)


class RestR3Dispatcher(Dispatcher):
    def __init__(self, conn):
        super().__init__(conn, RestR3Collector, RestR3Sender)


class RestR4Dispatcher(Dispatcher):
    def __init__(self, conn):
        super().__init__(conn, RestR4Collector, RestR4Sender)


class DealDispatcher(Dispatcher):
    def __init__(self, conn):
        super().__init__(conn, DealCollector, DealSender)
