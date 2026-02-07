from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration

from form_app.config import settings


class LineBotHelper:
    def __init__(self):
        self.handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
        self.configuration = Configuration(
            access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)


# Create the empty instance globally
line_bot_helper = LineBotHelper()
