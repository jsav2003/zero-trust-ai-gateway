import secrets
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

# auto_error=False so we can control the error shape ourselves instead of
# letting FastAPI raise a bare 403 when the header is absent.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Optional[str] = Security(_api_key_header)) -> None:
    """
    Zero-Trust gate for the scan endpoint.

    Fails closed: if no GATEWAY_API_KEY is configured the gateway refuses to
    serve rather than accepting everyone. Without that guard an unset key would
    make compare_digest("", "") authorize any caller.
    """
    expected = settings.GATEWAY_API_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key authentication is not configured on this gateway."
        )

    # Constant-time comparison to avoid leaking the key through timing analysis
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )
