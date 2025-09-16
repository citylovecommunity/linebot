from senders.dispatcher import (GoodbyeDispatcher, InvitationDispatcher,
                                LikedDispatcher, RestR1Dispatcher)
from senders_utils import load_bubble, send_bubble_to_member_id


def test_invitation(db_connection):
    InvitationDispatcher(db_connection).send_one()


def test_liked(db_connection):
    LikedDispatcher(db_connection).send_one()


def test_goodbye_bubble(db_connection):
    GoodbyeDispatcher(db_connection).send_one()


def test_rest_r1_bubble(db_connection):
    RestR1Dispatcher(db_connection).send_one()


def test_rest_r2_bubble(db_connection):

    list_of_users = get_list(db_connection, 'rest_r2')
    sender = RestR2Sender(db_connection, random.choice(list_of_users))
    sender.send()


def test_rest_r3_bubble(db_connection):
    list_of_users = get_list(db_connection, 'rest_r3')
    sender = RestR3Sender(db_connection, random.choice(list_of_users))
    sender.send()


def test_rest_r4_bubble(db_connection):
    list_of_users = get_list(db_connection, 'rest_r4')
    sender = RestR4Sender(db_connection, random.choice(list_of_users))
    sender.send()


def test_deal_bubble(db_connection):
    list_of_users = get_list(db_connection, 'deal')
    sender = DealSender(db_connection, random.choice(list_of_users))
    sender.send()


def test_send_bubble_to_member_id(db_connection):
    bubble = load_bubble('basic_bubble.json')

    stmt = """
    select id
    from member
    where phone_number not in (
        select phone_number
        from line_info
    )
    """
    with db_connection.cursor() as cur:
        result = cur.execute(stmt).fetchone()
    send_bubble_to_member_id(db_connection, result[0], bubble, '會員沒有綁定')
