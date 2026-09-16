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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
