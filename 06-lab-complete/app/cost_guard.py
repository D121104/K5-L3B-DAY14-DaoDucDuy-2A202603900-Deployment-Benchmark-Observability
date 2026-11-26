"""Daily token-cost budget stored in Redis."""
from datetime import datetime, time as datetime_time, timedelta, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _daily_key() -> str:
    return f"llm-cost-usd:{datetime.now(timezone.utc).date().isoformat()}"


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime_time.min, timezone.utc)
    return max(1, int((tomorrow - now).total_seconds()))


def check_budget() -> None:
    """Reject calls once today's accumulated cost has reached the configured budget."""
    try:
        spent = float(r.get(_daily_key()) or 0)
    except (redis.RedisError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (
        input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K
    ) / 1000
    key = _daily_key()
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(key, cost)
        pipe.expire(key, _seconds_until_utc_midnight())
        pipe.execute()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost recorder unavailable") from exc
    return cost
