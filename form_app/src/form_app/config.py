
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @property
    def is_dev(self):
        return self.APP_ENV == 'development'


settings = Settings()
