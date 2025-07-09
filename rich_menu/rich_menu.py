import requests
import os

TEST_USER_ID = os.getenv('TEST_USER_ID')
RICH_MENU_ID = os.getenv('RICH_MENU_ID')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')


def create_rich():
    url = "https://api.line.me/v2/bot/richmenu"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "size": {
            "width": 2500,
            "height": 1686
        },
        "selected": True,
        "name": "Test the per-user rich menu",
        "chatBarText": "Tap to open",
        "areas": [
            {
                "bounds": {
                    "x": 0,
                    "y": 0,
                    "width": 2500,
                    "height": 1686
                },
                "action": {
                    "type": "uri",
                    "label": "Tap area A",
                    "uri": "https://developers.line.biz/en/news/"
                }
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    # Output response
    print("Status Code:", response.status_code)
    print("Response Body:", response.text)


def upload_and_attach(image_path):
    url = f"https://api-data.line.me/v2/bot/richmenu/{RICH_MENU_ID}/content"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "image/png"
    }

    with open(image_path, 'rb') as image_file:
        response = requests.post(url, headers=headers, data=image_file)

    print("Status Code:", response.status_code)
    print("Response:", response.text)


def link_to_user():

    url = f"https://api.line.me/v2/bot/user/{TEST_USER_ID}/richmenu/{RICH_MENU_ID}"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers)

    print(response.status_code)
    print(response.text)
