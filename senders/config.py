import os

from dotenv import load_dotenv
from linebot import LineBotApi


load_dotenv()
DB = os.getenv('DB')
TEST_USER_ID = os.getenv("TEST_USER_ID")
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
FORM_WEB_URL = os.getenv("FORM_WEB_URL")
BUBBLE_HERO_IMAGE_URL = os.getenv("BUBBLE_HERO_IMAGE_URL")
ADMIN_LINE_ID = os.getenv('ADMIN_LINE_ID')
