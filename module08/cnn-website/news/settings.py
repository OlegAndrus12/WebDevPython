"""Every knob the app has, in one place, validated at import."""

from urllib.parse import quote_plus

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        str_strip_whitespace=True,
        extra="ignore",
    )

    # No default: the app must not start without a token.
    news_api_key: SecretStr
    news_api_url: str = "https://newsapi.org/v2"

    db_user: str = "admin"
    db_password: SecretStr = SecretStr("admin")
    db_host: str = "localhost"
    db_port: int = 5433
    db_name: str = "cnn"

    default_source: str = "cnn"
    page_size: int = 12

    @computed_field
    @property
    def database_url(self) -> str:
        # quote_plus: a URL is parsed by punctuation, so an @ or / in the
        # password would cut the string in the wrong place.
        password = quote_plus(self.db_password.get_secret_value())
        return (
            f"postgresql+psycopg://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
