import os

from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    TEMPLATES_AUTO_RELOAD = True
    SECRET_KEY = os.environ.get("secret_key")
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    DB = os.environ.get("DEV_DB_URL")


class ProductionConfig(BaseConfig):
    DEBUG = False
    DB = os.environ.get("PROD_DB_URL")
