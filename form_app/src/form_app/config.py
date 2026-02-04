import os

from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    TEMPLATES_AUTO_RELOAD = True
    SECRET_KEY = os.environ.get("secret_key")
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG")
    DB = os.environ.get("DB")
    TASK_SECRET = os.environ.get("TASK_SECRET")
    LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
    LINE_TEST_USER_ID = os.environ.get("TEST_USER_ID")
