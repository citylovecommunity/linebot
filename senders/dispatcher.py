import random

from collectors import (GoodbyeCollector, InvitationCollector, LikedCollector,
                        RestR1Collector)

from senders import (DealSender, GoodbyeSender, InvitationSender, LikedSender,
                     RestR1Sender, RestR2Sender, RestR3Sender, RestR4Sender)


class Dispatcher:
    def __init__(self, conn, collector, sender):
        self.conn = conn
        self.collector = collector(conn)
        self.sender = sender

    def send_all(self):
        list_of_users = self.collector.collect()
        for matching_row in list_of_users:
            self.sender(self.conn, matching_row).send()

    def send_one(self):
        list_of_users = self.collector.collect()
        self.sender(self.conn, random.choice(list_of_users)).send()


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
