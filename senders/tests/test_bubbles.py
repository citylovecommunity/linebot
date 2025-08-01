from sender import load_bubble, send_bubble, BUBBLE_MODIFIER, send_bubble_to_sub

from dotenv import load_dotenv
import os

load_dotenv()

TEST_USER_ID = os.getenv('TEST_USER_ID')


def test_invitation_bubble():
    bubble = load_bubble('invitation.json')
    bubble = BUBBLE_MODIFIER['invitation'](bubble, '')
    send_bubble(TEST_USER_ID, bubble, 'Test Invitation Bubble')


def test_send_bubble_to_sub():
    send_bubble_to_sub(None, 'test_member_id', load_bubble(
        'invitation.json'), 'Test Bubble to Sub')
