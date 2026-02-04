from config import ADMIN_LINE_ID, SENDER_PRODUCTION, TEST_USER_ID, line_bot_api
from linebot.models import QuickReply, QuickReplyButton, TextSendMessage
from linebot.models.actions import PostbackAction

import json


def arrived_message():
    return {
        "type": "text",
        "text": "你已經抵達約會地點了嗎？",
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "✅ 我已到",
                        "data": "action=arrived"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "⏰ 延後 5 分鐘",
                        "data": "action=delay"
                    }
                }
            ]
        }
    }


if __name__ == '__main__':
    message = TextSendMessage(
        text="你已經抵達約會地點了嗎？",
        quick_reply=QuickReply(
            items=[
                QuickReplyButton(
                    action=PostbackAction(
                        label="✅ 我已到",
                        data="action=arrived"
                    )
                ),
                QuickReplyButton(
                    action=PostbackAction(
                        label="⏰ 延後 5 分鐘",
                        data="action=delay"
                    )
                )
            ]
        )
    )
    line_bot_api.push_message(TEST_USER_ID, message)
