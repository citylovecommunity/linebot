
from enum import Enum

from pydantic_settings import BaseSettings


class AppEnvironment(str, Enum):
    DEV = "development"
    PROD = "production"
    TEST = "testing"


class Settings(BaseSettings):
    TEMPLATES_AUTO_RELOAD: bool = True
    SECRET_KEY: str
    APP_ENV: AppEnvironment = AppEnvironment.DEV
    DB: str
    TASK_SECRET: str
    LINE_CHANNEL_ACCESS_TOKEN: str
    LINE_CHANNEL_SECRET: str
    LINE_TEST_USER_ID: str
    APP_URL: str

    @property
    def DEBUG(self) -> bool:
        # Automatically enable debug if we are in development
        return self.APP_ENV == AppEnvironment.DEV

    @property
    def TESTING(self) -> bool:
        # Automatically enable testing mode if we are in testing
        return self.APP_ENV == AppEnvironment.TEST


settings = Settings()
