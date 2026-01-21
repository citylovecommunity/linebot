import os

from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    TEMPLATES_AUTO_RELOAD = True
    SECRET_KEY = os.environ.get("secret_key")
    DB = os.environ.get("DB")
