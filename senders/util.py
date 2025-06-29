import json
import os

import psycopg
from dotenv import load_dotenv
from linebot import LineBotApi
from linebot.models import FlexSendMessage

load_dotenv()

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

DB = os.getenv('DB')


def load_bubble(name):
    with open('bubbles/'+name) as file:
        bubble = json.load(file)
    return bubble


def send_bubble(user_id, bubble, alt_text='酷喔'):
    flex_message = FlexSendMessage(
        alt_text=alt_text,
        contents=bubble
    )
    line_bot_api.push_message(user_id, flex_message)


def get_responsible_id(member_id):
    stmt = """
    select user_id from
    line_info li
    join member m 
    on li.phone_number = m.phone_number
    where m.name =  ...
    """
    with psycopg.connect(DB) as conn:
        with conn.cursor() as cur:
            result = cur.execute(stmt, (member_id,)).fetchone()
            return result


def get_user_id(member_id):
    stmt = """
    select user_id from
    line_info li
    join member m 
    on li.phone_number = m.phone_number
    where m.id = %s   
    """
    with psycopg.connect(DB) as conn:
        with conn.cursor() as cur:
            result = cur.execute(stmt, (member_id,)).fetchone()
            return result


# send_bubble(load_bubble('female_restaurant.json'))
