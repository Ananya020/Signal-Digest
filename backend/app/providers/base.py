from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel


class Tick(BaseModel):
    ticker: str
    price: float
    volume: int
    timestamp: datetime
    source: Literal["real_historical", "replay_simulated", "fault_injected", "live_delayed_unofficial"]


class ProviderStatus(BaseModel):
    state: Literal["LIVE", "RECENT", "DELAYED", "STALE", "UNAVAILABLE"]
    last_successful_fetch: datetime
    age_seconds: float
    detail: str


class MarketDataProvider(Protocol):
    def get_ticks(self, tickers: list[str]) -> list[Tick]: ...
    def get_status(self) -> ProviderStatus: ...
