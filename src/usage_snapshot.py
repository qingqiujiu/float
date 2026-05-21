from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ModelUsage:
    model_name: str
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    completion_tokens: int = 0
    api_calls: int = 0
    cost: float = 0.0

    @property
    def prompt_tokens(self) -> int:
        return self.prompt_cache_hit_tokens + self.prompt_cache_miss_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class UsageSnapshot:
    fetched_at: datetime = field(default_factory=datetime.now)

    # balance
    total_balance: float = 0.0
    granted_balance: float = 0.0
    topped_up_balance: float = 0.0
    is_available: bool = False

    # token usage (all models combined)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # cost
    total_cost: float = 0.0

    # per-model breakdown
    models: list[ModelUsage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fetched_at": self.fetched_at.isoformat(),
            "total_balance": self.total_balance,
            "granted_balance": self.granted_balance,
            "topped_up_balance": self.topped_up_balance,
            "is_available": self.is_available,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "models": [
                {
                    "model_name": m.model_name,
                    "prompt_cache_hit_tokens": m.prompt_cache_hit_tokens,
                    "prompt_cache_miss_tokens": m.prompt_cache_miss_tokens,
                    "completion_tokens": m.completion_tokens,
                    "api_calls": m.api_calls,
                    "cost": m.cost,
                }
                for m in self.models
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UsageSnapshot":
        models = [
            ModelUsage(
                model_name=m["model_name"],
                prompt_cache_hit_tokens=m.get("prompt_cache_hit_tokens", 0),
                prompt_cache_miss_tokens=m.get("prompt_cache_miss_tokens", 0),
                completion_tokens=m.get("completion_tokens", 0),
                api_calls=m.get("api_calls", 0),
                cost=m.get("cost", 0.0),
            )
            for m in d.get("models", [])
        ]
        return cls(
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
            total_balance=d.get("total_balance", 0.0),
            granted_balance=d.get("granted_balance", 0.0),
            topped_up_balance=d.get("topped_up_balance", 0.0),
            is_available=d.get("is_available", False),
            prompt_tokens=d.get("prompt_tokens", 0),
            completion_tokens=d.get("completion_tokens", 0),
            total_tokens=d.get("total_tokens", 0),
            total_cost=d.get("total_cost", 0.0),
            models=models,
        )

    @classmethod
    def empty(cls) -> "UsageSnapshot":
        return cls()
