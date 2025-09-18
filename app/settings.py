import logging
from pydantic import computed_field, field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any


class Settings(BaseSettings):
    """
    Manages application settings using environment variables.
    Settings are loaded from a .env file and environment variables.
    """
    # Configure Pydantic to load from a .env file if it exists
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LOG_LEVEL: str = "INFO"
    MOTOTWIST_SECRET_KEY: str = "mototwist"
    MOTOTWIST_ADMIN_EMAIL: str = "admin@admin.com"
    MOTOTWIST_ADMIN_PASSWORD: str = "password"
    OSM_URL: str = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    OSRM_URL: str = "https://router.project-osrm.org"
    TWIST_SIMPLIFICATION_TOLERANCE_M: int = Field(default=0)

    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "mototwist"
    POSTGRES_USER: str = "mototwist"
    POSTGRES_PASSWORD: str = "password"

    REDIS_URL: str = "redis://redis:6379"


    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        """Construct the database URL from individual components."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validates that LOG_LEVEL is a valid Python logging level."""
        # Get valid log levels directly from the logging module
        valid_levels = list(logging.getLevelNamesMapping().keys())

        upper_value = value.upper()
        if upper_value not in valid_levels:
            raise ValueError(
                f"Invalid LOG_LEVEL: '{value}'. "
                f"Must be one of {valid_levels}"
            )
        return upper_value

    @field_validator("TWIST_SIMPLIFICATION_TOLERANCE_M", mode="before")
    @classmethod
    def parse_tolerance_from_string(cls, value: Any) -> int:
        """Parses an integer from a string like '10m' or '25'."""
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip().rstrip("mM"))
            except (ValueError, TypeError):
                raise ValueError(f"Invalid tolerance value: '{value}'")
        raise TypeError("Tolerance value must be a string or integer.")


# Create a single, importable instance of the settings
settings = Settings()