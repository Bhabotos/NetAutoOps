from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env."""

    database_url: str
    log_level: str = "INFO"

    # Phase 3: shared lab SSH credential used by Netmiko to read device health.
    # A per-device secrets vault is planned for a later phase; for now the
    # inventory only stores usernames (see app/models/device.py), and the
    # password/enable-secret come solely from the environment.
    device_ssh_password: str | None = None
    device_enable_secret: str | None = None
    netmiko_timeout: int = 10
    tcp_check_timeout: float = 3.0

    # Phase 4: configuration backups can be much larger/slower to print than
    # the Phase 3 show commands, so they get their own read timeout.
    backup_command_timeout: int = 60

    # Phase 5: n8n webhook integration for automation events. Left unset by
    # default -- event delivery is then a safe no-op (logged, never sent)
    # rather than pointing at nothing.
    n8n_webhook_url: str | None = None
    n8n_webhook_timeout: float = 5.0
    n8n_webhook_max_retries: int = 3
    n8n_webhook_retry_backoff_seconds: float = 1.0

    # Phase 7: interface discovery output is typically smaller than a full
    # running-config but larger than a single show version/cpu/memory line.
    interfaces_command_timeout: int = 30

    # Phase 8: scheduled automated checks. Disable entirely with
    # SCHEDULER_ENABLED=false (e.g. for one-off scripts that shouldn't run a
    # background scheduler); the test suite never triggers the app's
    # startup lifecycle at all, so it never starts the scheduler regardless
    # of this setting.
    scheduler_enabled: bool = True
    health_check_interval_minutes: int = 15
    backup_interval_minutes: int = 1440
    interface_check_interval_minutes: int = 15

    # Phase 9: JWT authentication. jwt_secret_key has no default -- it must be
    # set explicitly in .env (generate one with
    # `python -c "import secrets; print(secrets.token_hex(32))"`). Tokens
    # never embed a role; app/api/deps.py always re-reads role/is_active from
    # the database on every request.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
