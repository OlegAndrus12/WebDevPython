"""Every knob the app has, in one place, validated at import.

`SecretStr` is the reason to use pydantic-settings rather than `os.environ`: a
plain `str` token ends up in every traceback frame and `repr()`. It prints as
`**********` and only yields the value to an explicit `.get_secret_value()`.
"""

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
    # 5435 is the host-side view. Inside compose the api container overrides
    # this to db:5432, where the database is a service name, not a published port.
    db_port: int = 5435
    db_name: str = "cnn"

    # Which NewsAPI source the front page shows when there is no ?q=.
    default_source: str = "cnn"
    # How many articles to ask NewsAPI for, not how many a JSON page returns.
    page_size: int = 12

    @computed_field
    @property
    def database_url(self) -> str:
        """The SQLAlchemy URL, assembled from the pieces above."""
        # quote_plus: a URL is parsed by punctuation, so a password containing
        # @ or / would cut the string in the wrong place.
        password = quote_plus(self.db_password.get_secret_value())
        return (
            f"postgresql+psycopg://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
