import os

# Set before any app module is imported: Settings is a module-level singleton,
# and environment variables take precedence over a developer's local .env, so
# this keeps the suite hermetic regardless of what is configured locally.
os.environ["GATEWAY_API_KEY"] = "test-api-key"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost:5432/test_db"

# GOOGLE_API_KEY is deliberately not set: get_llm() is lazy, and no test ever
# builds the Gemini client. The SQLAlchemy engine is lazy too, so no connection
# is opened by importing the app.

API_KEY_HEADER = {"X-API-Key": "test-api-key"}
