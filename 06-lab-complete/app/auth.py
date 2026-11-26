"""API-key authentication for protected endpoints."""
import hmac

from fastapi import Header, HTTPException, status


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Dependency cho FastAPI — dùng trong /ask: Depends(verify_api_key)."""
    from app.config import settings

    if not settings.agent_api_key or not x_api_key or not hmac.compare_digest(
        x_api_key, settings.agent_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
