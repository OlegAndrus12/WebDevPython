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

    news_api_key: SecretStr
    news_api_url: str = "https://newsapi.org/v2"

    db_user: str = "admin"
    db_password: SecretStr = SecretStr("admin")
    db_host: str = "localhost"
    db_port: int = 5411
    db_name: str = "cnn"

    default_source: str = "cnn"
    page_size: int = 12

    # FastAPI's debug mode and the debug toolbar's switch, which reads app.debug.
    debug: bool = False

    secret_key: SecretStr
    access_token_expire_minutes: int = 60
    verification_token_expire_minutes: int = 60

    redis_host: str = "localhost"
    redis_port: int = 6311
    article_cache_ttl_seconds: int = 300

    rate_limit_window_seconds: int = 1

    mail_server: str = "localhost"
    mail_port: int = 1011
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@cnnreader.example"
    mail_from_name: str = "CNN Reader"
    mail_starttls: bool = False
    mail_ssl_tls: bool = False
    mail_use_credentials: bool = False
    mail_validate_certs: bool = False

    celery_broker_db: int = 1
    celery_result_db: int = 2
    celery_result_expires_seconds: int = 3600

    public_base_url: str = "http://localhost:8011/"

    newsletter_hour: int = 8
    newsletter_minute: int = 0
    newsletter_max_articles: int = 10

    stats_report_hour: int = 7
    stats_report_minute: int = 0

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @computed_field
    @property
    def celery_broker_url(self) -> str:
        """Where tasks are queued. Database 1, never the cache's 0."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.celery_broker_db}"

    @computed_field
    @property
    def celery_result_backend(self) -> str:
        """Where task results land. Database 2, so a broker flush spares them."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.celery_result_db}"

    @computed_field
    @property
    def database_url(self) -> str:
        """The SQLAlchemy URL, assembled from the pieces above."""
        password = quote_plus(self.db_password.get_secret_value())
        return (
            f"postgresql+psycopg://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
