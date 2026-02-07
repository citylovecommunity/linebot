
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TEMPLATES_AUTO_RELOAD: bool = True
    SECRET_KEY: str
    APP_ENV: Literal["development", "production"] = "development"
    DB: str
    TASK_SECRET: str
    LINE_CHANNEL_ACCESS_TOKEN: str
    LINE_CHANNEL_SECRET: str
    LINE_TEST_USER_ID: str
    APP_URL: str


settings = Settings()
