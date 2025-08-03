from utils import load_bubble, send_bubble, send_bubble_to_sub
from bubble_modifiers import BUBBLE_MODIFIER
from dotenv import load_dotenv
from utils import get_list
from config import DB
import os
import json
import psycopg

load_dotenv()

TEST_USER_ID = os.getenv('TEST_USER_ID')


def test_invitation_bubble():
    bubble = load_bubble('invitation.json')
    with psycopg.connect(DB) as conn:
        list_of_users = get_list(conn, 'invitation')
        bubble = BUBBLE_MODIFIER['invitation'](conn, bubble, list_of_users[0])
        # print(json.dumps(bubble, indent=2, ensure_ascii=False))
        send_bubble(TEST_USER_ID, bubble, 'Test Invitation Bubble')


def test_send_bubble_to_sub():
    send_bubble_to_sub(None, 'test_member_id', load_bubble(
        'invitation.json'), 'Test Bubble to Sub')
