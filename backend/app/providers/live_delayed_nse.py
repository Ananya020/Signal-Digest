"""LiveDelayedNSEProvider — Workstream 3, opt-in, additive only.

## Why this exists, stated plainly (see PRODUCT.md's "Data source" section)

There is no legitimate free live NSE data source. Zerodha's Kite Connect
(₹500/month) requires an active KYC'd trading account and a static IP —
neither obtainable in this build's timeframe. Unofficial scrapers of NSE's
own website (e.g. nsepython) are explicitly undocumented/unsupported and
have real, currently-reported breakage. This provider deliberately does NOT
attempt to scrape nseindia.com directly — verified against the real site
before building anything: a plain request to https://www.nseindia.com/
returns an immediate 403 from this environment (Cloudflare/bot-protection),
before even getting to NSE's quote API. That's a dead end, reported here
rather than built around.

## What this actually uses instead

`yfinance` — already a vetted, working dependency in this project (the
historical backfill's data source) — also serves an intraday, exchange-
delayed (Yahoo's own delay, typically ~15 minutes during market hours; the
last completed session's data outside market hours) 1-minute-bar feed via
`Ticker.history(period="1d", interval="1m")`. Verified working with a real
request against RELIANCE.NS before this was built: it returned 361 real
1-minute bars for the most recent trading session. This is still an
unofficial, undocumented-for-this-use surface (Yahoo doesn't publish an API
contract for it, and yfinance itself scrapes/reverse-engineers Yahoo's
internal endpoints) — genuinely the same class of fragility RELIABILITY.md
already designs for, just a different upstream than the historical-replay
provider's one-time backfill use of the same library.

## Design — no special-casing, same freshness machinery

Implements the exact `MarketDataProvider` protocol (`get_ticks`,
`get_status`) with NO new error-handling path: `get_status()` reuses
`classify_freshness()` — the identical function `FaultInjectingProvider`
uses — against `age = now - last_successful_fetch`. Before any fetch has
ever succeeded, `last_successful_fetch` is `None` and `get_status()` reports
`UNAVAILABLE`, mirroring `FaultInjectingProvider`'s own "no real data to
show" hard-failure branch, not a new state. A failed or malformed fetch
(exception, empty response, missing columns) is swallowed per-ticker inside
`get_ticks()` and simply contributes no `Tick` for that ticker — the exact
same shape as `HistoricalReplayProvider.get_ticks()` skipping a ticker whose
history is exhausted at the current step. No retry/backoff: one request per
ticker per call, a 5s socket timeout, nothing more — engineering around the
fragility here would defeat the point of using it as a live reliability
demonstration.

## Status-only by design (see PRODUCT.md decision, Workstream 3)

This provider is constructed at startup when `LIVE_PROVIDER_ENABLED=true`,
but is NEVER wired into `run_scoring_cycle`/the scheduler — it does not feed
`price_ticks`, baselines, or flags. It's reachable only via
`GET /provider/live-status`, which calls it on demand. Recommendation
(documented in PRODUCT.md): keep it demonstration/status-only rather than
scoring off it — mixing a fragile, occasionally-empty real feed into the
baseline computation the whole scoring engine depends on is a real
correctness risk for no demo benefit; the abstraction point is already fully
proven by a real `get_ticks()`/`get_status()` call succeeding or failing
honestly through the existing freshness states.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.providers.base import ProviderStatus, Tick
from app.services.freshness import classify_freshness

FETCH_TIMEOUT_SECONDS = 5


@dataclass
class LiveDelayedNSEProvider:
    live_seconds: float
    recent_seconds: float
    delayed_seconds: float
    stale_seconds: float
    last_successful_fetch: datetime | None = None
    last_detail: str = field(default="no fetch attempted yet")

    def get_ticks(self, tickers: list[str]) -> list[Tick]:
        ticks: list[Tick] = []
        failures: list[str] = []
        for ticker in tickers:
            try:
                tick = self._fetch_one(ticker)
            except Exception as e:  # noqa: BLE001 — a single ticker's fetch failing must not abort the batch
                failures.append(f"{ticker}: {e}")
                continue
            if tick is not None:
                ticks.append(tick)
            else:
                failures.append(f"{ticker}: no usable data returned")

        if ticks:
            self.last_successful_fetch = datetime.now(timezone.utc)
            self.last_detail = f"live_delayed_unofficial: fetched {len(ticks)}/{len(tickers)} tickers"
            if failures:
                self.last_detail += f" ({len(failures)} failed: {'; '.join(failures[:3])})"
        else:
            self.last_detail = f"live_delayed_unofficial: fetch failed for all {len(tickers)} tickers" + (
                f" ({'; '.join(failures[:3])})" if failures else ""
            )
        return ticks

    def _fetch_one(self, ticker: str) -> Tick | None:
        # Imported lazily so a missing/broken yfinance install only breaks
        # this opt-in path, never the app's default startup.
        import yfinance as yf

        data = yf.Ticker(ticker).history(period="1d", interval="1m", timeout=FETCH_TIMEOUT_SECONDS)
        if data.empty:
            return None

        last = data.iloc[-1]
        if last[["Close", "Volume"]].isna().any():
            return None  # malformed row — same "no usable data" outcome as empty

        ts = data.index[-1].to_pydatetime()
        return Tick(
            ticker=ticker,
            price=float(last["Close"]),
            volume=int(last["Volume"]),
            timestamp=ts,
            source="live_delayed_unofficial",
        )

    def get_status(self) -> ProviderStatus:
        now = datetime.now(timezone.utc)
        if self.last_successful_fetch is None:
            # No successful fetch has ever occurred — the exact same
            # "nothing real to show" state FaultInjectingProvider's outage
            # branch reports, not a new one.
            return ProviderStatus(state="UNAVAILABLE", last_successful_fetch=now, age_seconds=0.0, detail=self.last_detail)

        age = (now - self.last_successful_fetch).total_seconds()
        state = classify_freshness(age, self.live_seconds, self.recent_seconds, self.delayed_seconds, self.stale_seconds)
        return ProviderStatus(state=state, last_successful_fetch=self.last_successful_fetch, age_seconds=age, detail=self.last_detail)
