from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, MessagingApi

from form_app.config import BaseConfig


class LineBotHelper:
    def __init__(self):
        self.handler = WebhookHandler(BaseConfig.LINE_CHANNEL_SECRET)
        self.configuration = Configuration(
            access_token=BaseConfig.LINE_CHANNEL_ACCESS_TOKEN)


# Create the empty instance globally
line_bot_helper = LineBotHelper()
