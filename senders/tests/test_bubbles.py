from utils import load_bubble, send_bubble, send_bubble_to_sub
from bubble_modifiers import BUBBLE_MODIFIER
from dotenv import load_dotenv
from utils import get_list
from config import DB
import os
import json
import psycopg
import random

load_dotenv()

TEST_USER_ID = os.getenv('TEST_USER_ID')


def test_invitation_bubble():
    bubble = load_bubble('invitation.json')
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'invitation')
        bubble = BUBBLE_MODIFIER['invitation'](
            conn, bubble, random.choice(list_of_users))
        # print(json.dumps(bubble, indent=2, ensure_ascii=False))
        send_bubble(TEST_USER_ID, bubble, 'Test Invitation Bubble')


def test_send_bubble_to_sub():
    bubble = load_bubble('invitation.json')

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
        send_bubble_to_sub(conn, result[0], bubble, '會員沒有綁定')
