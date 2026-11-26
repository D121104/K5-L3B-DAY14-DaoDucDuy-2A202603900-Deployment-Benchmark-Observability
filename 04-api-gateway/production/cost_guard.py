"""Monthly per-user and global LLM budgets backed by Redis."""
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Reference prices per 1,000 tokens (GPT-4o-mini).
PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006


def _current_month_and_ttl() -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return now.strftime("%Y-%m"), max(1, int((next_month - now).total_seconds()))


@dataclass
class UsageRecord:
    user_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    month: str = ""
    cost_usd: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.cost_usd


class CostGuard:
    def __init__(
        self,
        monthly_budget_per_user_usd: float = 10.0,
        global_monthly_budget_usd: float = 100.0,
        warn_at_pct: float = 0.8,
        redis_url: str | None = None,
        key_prefix: str = "day14:cost-guard",
        redis_client: redis.Redis | None = None,
    ):
        self.monthly_budget_per_user_usd = monthly_budget_per_user_usd
        self.global_monthly_budget_usd = global_monthly_budget_usd
        self.warn_at_pct = warn_at_pct
        self.key_prefix = key_prefix
        self.redis = redis_client or redis.Redis.from_url(
            redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
        )

    def _user_key(self, user_id: str, month: str) -> str:
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()
        return f"{self.key_prefix}:{month}:user:{user_hash}"

    def _global_key(self, month: str) -> str:
        return f"{self.key_prefix}:{month}:global"

    @staticmethod
    def _record(user_id: str, month: str, data: dict[str, str]) -> UsageRecord:
        input_tokens = int(data.get("input_tokens", 0))
        output_tokens = int(data.get("output_tokens", 0))
        calculated_cost = (
            input_tokens * PRICE_PER_1K_INPUT_TOKENS
            + output_tokens * PRICE_PER_1K_OUTPUT_TOKENS
        ) / 1000
        return UsageRecord(
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_count=int(data.get("request_count", 0)),
            month=month,
            cost_usd=float(data.get("cost_usd", calculated_cost)),
        )

    def _get_record(self, user_id: str) -> UsageRecord:
        month, _ = _current_month_and_ttl()
        try:
            data = self.redis.hgetall(self._user_key(user_id, month))
        except redis.RedisError as exc:
            raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
        return self._record(user_id, month, data)

    def check_budget(self, user_id: str, estimated_cost: float) -> bool:
        """Atomically reserve estimated spend if both monthly budgets allow it."""
        if estimated_cost < 0:
            raise ValueError("Estimated cost must not be negative")
        month, _ = _current_month_and_ttl()
        _, ttl = _current_month_and_ttl()
        user_key = self._user_key(user_id, month)
        global_key = self._global_key(month)
        reserve_script = """
        local user_cost = tonumber(redis.call('HGET', KEYS[1], 'cost_usd') or '0')
        local global_cost = tonumber(redis.call('HGET', KEYS[2], 'cost_usd') or '0')
        local estimate = tonumber(ARGV[1])
        if user_cost + estimate > tonumber(ARGV[2]) then return 0 end
        if global_cost + estimate > tonumber(ARGV[3]) then return 0 end
        for i = 1, 2 do
          redis.call('HINCRBYFLOAT', KEYS[i], 'cost_usd', estimate)
          redis.call('HINCRBYFLOAT', KEYS[i], 'reserved_cost_usd', estimate)
          redis.call('EXPIRE', KEYS[i], tonumber(ARGV[4]))
        end
        return 1
        """
        try:
            allowed = self.redis.eval(
                reserve_script,
                2,
                user_key,
                global_key,
                estimated_cost,
                self.monthly_budget_per_user_usd,
                self.global_monthly_budget_usd,
                ttl,
            )
        except redis.RedisError as exc:
            raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
        if not allowed:
            return False

        record = self._get_record(user_id)
        if record.total_cost_usd >= self.monthly_budget_per_user_usd * self.warn_at_pct:
            logger.warning("User monthly budget is at least %.0f%% used", self.warn_at_pct * 100)
        return True

    def record_usage(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost: float = 0.0,
    ) -> UsageRecord:
        """Replace a reservation with actual token cost and record usage."""
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token counts must not be negative")
        if estimated_cost < 0:
            raise ValueError("Estimated cost must not be negative")

        month, ttl = _current_month_and_ttl()
        user_key = self._user_key(user_id, month)
        global_key = self._global_key(month)
        actual_cost = (
            input_tokens * PRICE_PER_1K_INPUT_TOKENS
            + output_tokens * PRICE_PER_1K_OUTPUT_TOKENS
        ) / 1000
        adjustment = actual_cost - estimated_cost
        try:
            with self.redis.pipeline(transaction=True) as pipe:
                for key in (user_key, global_key):
                    pipe.hincrby(key, "input_tokens", input_tokens)
                    pipe.hincrby(key, "output_tokens", output_tokens)
                    pipe.hincrby(key, "request_count", 1)
                    pipe.hincrbyfloat(key, "cost_usd", adjustment)
                    pipe.hincrbyfloat(key, "reserved_cost_usd", -estimated_cost)
                    pipe.expire(key, ttl)
                pipe.execute()
        except redis.RedisError as exc:
            raise HTTPException(status_code=503, detail="Cost recorder unavailable") from exc

        record = self._get_record(user_id)
        if record.total_cost_usd >= self.monthly_budget_per_user_usd * self.warn_at_pct:
            logger.warning("User monthly budget is at least %.0f%% used", self.warn_at_pct * 100)
        return record

    def release_reservation(self, user_id: str, estimated_cost: float) -> None:
        """Release estimated spend if the LLM call fails before usage is recorded."""
        month, _ = _current_month_and_ttl()
        try:
            with self.redis.pipeline(transaction=True) as pipe:
                for key in (self._user_key(user_id, month), self._global_key(month)):
                    pipe.hincrbyfloat(key, "cost_usd", -estimated_cost)
                    pipe.hincrbyfloat(key, "reserved_cost_usd", -estimated_cost)
                pipe.execute()
        except redis.RedisError as exc:
            raise HTTPException(status_code=503, detail="Cost reservation cleanup failed") from exc

    @property
    def _global_cost(self) -> float:
        month, _ = _current_month_and_ttl()
        try:
            data = self.redis.hgetall(self._global_key(month))
        except redis.RedisError as exc:
            raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
        return self._record("global", month, data).total_cost_usd

    def get_usage(self, user_id: str) -> dict:
        record = self._get_record(user_id)
        cost = record.total_cost_usd
        return {
            "user_id": user_id,
            "month": record.month,
            "requests": record.request_count,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cost_usd": round(cost, 6),
            "budget_usd": self.monthly_budget_per_user_usd,
            "budget_remaining_usd": max(0, self.monthly_budget_per_user_usd - cost),
            "budget_used_pct": round(cost / self.monthly_budget_per_user_usd * 100, 1),
        }


cost_guard = CostGuard()


def check_budget(user_id: str, estimated_cost: float) -> bool:
    """Exercise 4.4 interface: reserve estimated monthly spend in Redis."""
    return cost_guard.check_budget(user_id, estimated_cost)
