import psycopg
from collectors import (ChangeTimeCollector, Collector,
                        DatingFeedbackCollector, DatingNotificationCollector,
                        Deal1DCollector, Deal3HRCollector, DealCollector,
                        GoodbyeCollector, Invitation24Collector,
                        Invitation48Collector, InvitationCollector,
                        Liked24Collector, Liked48Collector, LikedCollector,
                        NextMonthCollector, NoActionGoodbyeCollector,
                        RestR1Collector, RestR1NextMonthCollector,
                        RestR2Collector, RestR3Collector, RestR4Collector,
                        RestR124Collector, RestR148Collector,
                        RestR224Collector, RestR248Collector,
                        RestR324Collector, RestR348Collector,
                        RestR424Collector, RestR448Collector,
                        SuddenChangeTimeCollector)

from senders import (ChangeTimeSender, DatingFeedbackSender,
                     DatingNotificationSender, Deal1DDealSender, Deal3HRSender,
                     DealSender, GoodbyeSender, Invitation24Sender,
                     Invitation48Sender, InvitationSender, Liked24Sender,
                     Liked48Sender, LikedSender, NextMonthSender,
                     NoActionGoodbyeSender, RestR1NextMonthSender,
                     RestR1Sender, RestR2Sender, RestR3Sender, RestR4Sender,
                     RestR124Sender, RestR148Sender, RestR224Sender,
                     RestR248Sender, RestR324Sender, RestR348Sender,
                     RestR424Sender, RestR448Sender, Sender,
                     SuddenChangeTimeSender)


class Dispatcher:
    def __init__(self, conn: psycopg.Connection, collector: Collector, sender: Sender):
        self.conn = conn
        self.collector = collector(conn)
        self.sender = sender

        self._users = self.collector.collect()

    def show_collection(self):
        return self._users

    def send_all(self, change_state=None):
        for matching_row in self._users:
            self.sender(self.conn, matching_row).send(change_state)

    def send_one(self, change_state=None):
        self.sender(self.conn, self._users[0]).send(change_state)


# Mapping of dispatcher types to their collector and sender classes
DISPATCHER_MAP = {
    'invitation': (InvitationCollector, InvitationSender),
    'invitation_24': (Invitation24Collector, Invitation24Sender),
    'invitation_48': (Invitation48Collector, Invitation48Sender),
    'liked': (LikedCollector, LikedSender),
    'liked_24': (Liked24Collector, Liked24Sender),
    'liked_48': (Liked48Collector, Liked48Sender),
    'goodbye': (GoodbyeCollector, GoodbyeSender),
    'rest_r1': (RestR1Collector, RestR1Sender),
    'rest_r1_24': (RestR124Collector, RestR124Sender),
    'rest_r1_48': (RestR148Collector, RestR148Sender),
    'rest_r2': (RestR2Collector, RestR2Sender),
    'rest_r2_24': (RestR224Collector, RestR224Sender),
    'rest_r2_48': (RestR248Collector, RestR248Sender),
    'rest_r3': (RestR3Collector, RestR3Sender),
    'rest_r3_24': (RestR324Collector, RestR324Sender),
    'rest_r3_48': (RestR348Collector, RestR348Sender),
    'rest_r4': (RestR4Collector, RestR4Sender),
    'rest_r4_24': (RestR424Collector, RestR424Sender),
    'rest_r4_48': (RestR448Collector, RestR448Sender),
    'deal': (DealCollector, DealSender),
    'no_action_goodbye': (NoActionGoodbyeCollector, NoActionGoodbyeSender),
    'deal_1d_notification': (Deal1DCollector, Deal1DDealSender),
    'deal_3hr_notification': (Deal3HRCollector, Deal3HRSender),
    'sudden_change_time_notification': (SuddenChangeTimeCollector, SuddenChangeTimeSender),
    'next_month': (NextMonthCollector, NextMonthSender),
    'change_time': (ChangeTimeCollector, ChangeTimeSender),
    'rest_r1_next_month': (RestR1NextMonthCollector, RestR1NextMonthSender),
    'dating_notification': (DatingNotificationCollector, DatingNotificationSender),
    'dating_feedback': (DatingFeedbackCollector, DatingFeedbackSender)
}


def get_dispatcher(dispatcher_type: str, conn: psycopg.Connection) -> Dispatcher:
    if dispatcher_type not in DISPATCHER_MAP:
        raise ValueError(f"Unknown dispatcher type: {dispatcher_type}")
    collector, sender = DISPATCHER_MAP[dispatcher_type]
    return Dispatcher(conn, collector, sender)
