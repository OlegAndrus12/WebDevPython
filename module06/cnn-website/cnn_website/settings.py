"""Every knob the app has, in one place, validated at import.

The reference app read its token with `os.environ.get("NEWS_API_KEY")`, which
gives you `None` when the variable is missing and a 401 from NewsAPI ten
seconds later. `BaseSettings` fails immediately instead, and names the field
that is missing.

`SecretStr` is the reason to reach for pydantic-settings here rather than
`os.environ`: a plain `str` token ends up in every traceback frame, every
`repr()`, and every debugger watch window. `SecretStr` prints as `**********`
and only gives up the value to an explicit `.get_secret_value()`.
"""

from urllib.parse import quote_plus

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from the environment first, then `.env`. Env wins -- that is what
    lets compose.yaml override `database_url` without editing the file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        str_strip_whitespace=True,
        # Ignore unrelated variables
        extra="ignore",
    )

    # No default: the app must not start without a token.
    news_api_key: SecretStr
    news_api_url: str = "https://newsapi.org/v2"

    # The connection in pieces rather than one URL string. Compose needs the
    # same values split up anyway -- POSTGRES_USER, POSTGRES_DB, the published
    # port -- and keeping one URL here plus those there is how the app and its
    # database end up disagreeing about which is which.
    db_user: str = "admin"
    db_password: SecretStr = SecretStr("admin")
    # localhost:5433 is the host-side view, for `uv run flask ...`. Inside
    # compose the web container sets DB_HOST=db and DB_PORT=5432, because there
    # the database is a service name on the compose network, not a published
    # port on your machine.
    db_host: str = "localhost"
    db_port: int = 5433
    db_name: str = "cnn"

    # Which NewsAPI source the front page shows when there is no ?q=.
    default_source: str = "cnn"
    page_size: int = 12

    # Flask needs this for session cookies. Fine as a default in a teaching
    # project; in production it comes from the environment like the token.
    secret_key: SecretStr = SecretStr("dev-only-not-a-real-secret")


    @computed_field
    @property
    def database_url(self) -> str:
        """The SQLAlchemy URL, assembled from the pieces above.

        `postgresql+psycopg` selects psycopg 3, the same driver as
        ../postgres/db.py.

        `quote_plus` on the password: a URL is parsed by punctuation, so a
        password containing `@`, `/` or `#` would otherwise cut the string in
        the wrong place and produce a baffling "could not translate host name"
        rather than an authentication error.
        """
        password = quote_plus(self.db_password.get_secret_value())
        return (
            f"postgresql+psycopg://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


# One instance, imported by db.py, views.py, migrations/env.py and the factory.
# Constructed at import, so a bad .env fails the process rather than the first
# request that happens to need the token.
settings = Settings()
