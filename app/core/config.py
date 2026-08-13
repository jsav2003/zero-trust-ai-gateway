from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Enterprise Application Settings.
    Loads and validates environment variables with strong typing via Pydantic.
    """
    # Application Environment
    ENV: str = Field(default="development", description="Deployment environment (dev, staging, prod).")
    
    # Database Configuration
    # Notice the 'postgresql+asyncpg' prefix required for asynchronous I/O operations
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/gateway_db",
        description="Asynchronous PostgreSQL connection string."
    )

    # Google AI Configuration
    GOOGLE_API_KEY: str = Field(
        default="", 
        description="Google API Key for Gemini."
    )

    # Configuration for loading from .env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extraneous variables in the .env file
    )

# Singleton instance to be imported across modules
settings = Settings()
