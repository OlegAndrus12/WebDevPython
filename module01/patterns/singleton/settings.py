

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import dotenv_values

@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    secret_key: str
    debug: bool = False
    allowed_hosts: tuple[str, ...] = field(default_factory=lambda: ("localhost",))

    def __repr__(self) -> str:
        return (
            f"Settings(database_url={self.database_url!r}, "
            f"secret_key='***', debug={self.debug}, "
            f"allowed_hosts={self.allowed_hosts!r})"
        )

    @classmethod
    def from_env(cls) -> Settings:
        env = dotenv_values(".env")

        debug = env.get("DEBUG", "false").lower() in {"1", "true", "yes"}
        secret_key = env.get("SECRET_KEY", "")

        if not debug and not secret_key:
            raise RuntimeError("SECRET_KEY is required when DEBUG is off")

        return cls(
            database_url=env.get("DATABASE_URL", "postgresql://localhost/app"),
            secret_key=secret_key or "dev-only-insecure-key",
            debug=debug,
            allowed_hosts=tuple(
                host.strip()
                for host in env.get("ALLOWED_HOSTS", "localhost").split(",")
                if host.strip()
            ),
        )

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


if __name__ == "__main__":
    a = get_settings()
    b = get_settings()

    print(a is b, a.database_url, a.debug)
    print(a)

    # .env was read once; the second call was a cache hit, not a re-read.
    print(get_settings.cache_info())
