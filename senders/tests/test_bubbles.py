import random

import psycopg
from bubble_senders import (DealSender, GoodByeSender, InvitationSender, LikedSender,
                            RestR1Sender, RestR2Sender, RestR3Sender,
                            RestR4Sender)
from config import DB
from senders_utils import get_list, load_bubble, send_bubble_to_member_id


def test_invitation_bubble():
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'invitation')
        sender = InvitationSender(conn, random.choice(list_of_users))
        sender.send()


def test_liked_bubble():
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'liked')
        sender = LikedSender(conn, random.choice(list_of_users))
        sender.send()


def test_goodbye_bubble():
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'goodbye')
        sender = GoodByeSender(conn, random.choice(list_of_users))
        sender.send()


def test_rest_r1_bubble():
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'rest_r1')
        sender = RestR1Sender(conn, random.choice(list_of_users))
        sender.send()


def test_rest_r2_bubble():
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'rest_r2')
        sender = RestR2Sender(conn, random.choice(list_of_users))
        sender.send()


def test_rest_r3_bubble():
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'rest_r3')
        sender = RestR3Sender(conn, random.choice(list_of_users))
        sender.send()


def test_rest_r4_bubble():
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'rest_r4')
        sender = RestR4Sender(conn, random.choice(list_of_users))
        sender.send()


def test_deal_bubble():
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'deal')
        sender = DealSender(conn, random.choice(list_of_users))
        sender.send()


def test_send_bubble_to_member_id():
    bubble = load_bubble('basic_bubble.json')

    with psycopg.connect(DB) as conn:
        stmt = """
        select id
        from member
        where phone_number not in (
            select phone_number
            from line_info
        )
        """
        with conn.cursor() as cur:
            result = cur.execute(stmt).fetchone()
        send_bubble_to_member_id(conn, result[0], bubble, '會員沒有綁定')
