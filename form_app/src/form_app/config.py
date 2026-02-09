
from typing import Literal, Optional


from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TEMPLATES_AUTO_RELOAD: bool = True
    SECRET_KEY: str
    APP_ENV: Literal["development", "production"] = "development"

    TASK_SECRET: str
    LINE_CHANNEL_ACCESS_TOKEN: str
    LINE_CHANNEL_SECRET: str

    LINE_TEST_USER_ID: Optional[str] = None

    DEV_DB_URL: Optional[str] = None
    PROD_DB_URL: Optional[str] = None

    PROD_FORM_WEB_URL: Optional[str] = None
    DEV_FORM_WEB_URL: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @property
    def is_dev(self):
        return self.APP_ENV == 'development'

    @property
    def DB(self) -> str:
        if self.APP_ENV == 'production':
            if not self.PROD_DB_URL:
                raise ValueError(
                    "Cannot start in production: PROD_DB_URL is missing!")
            return self.PROD_DB_URL

        # Default to Development
        if not self.DEV_DB_URL:
            raise ValueError("DEV_DB_URL is missing!")
        return self.DEV_DB_URL

    @property
    def APP_URL(self) -> str:
        if self.APP_ENV == 'production':
            if not self.PROD_FORM_WEB_URL:
                raise ValueError(
                    "Cannot start in production: PROD_FORM_WEB_URL is missing!")
            return self.PROD_FORM_WEB_URL

        # Default to Development
        if not self.DEV_FORM_WEB_URL:
            raise ValueError("DEV_FORM_WEB_URL is missing!")
        return self.DEV_FORM_WEB_URL


settings = Settings()
