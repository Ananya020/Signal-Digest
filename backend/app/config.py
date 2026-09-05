from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    demo_mode: bool = False
    frontend_origin: str = "http://localhost:3000"

    # Deployment hardening, additive to demo_mode (see admin.py) — never a
    # replacement for it. Unset (None/empty, the default, matching local
    # dev's .env.example) disables the extra check entirely: /admin/fault
    # behaves exactly as it always has, gated on demo_mode alone. Only a
    # public deployment that sets a real value gains the extra shared-secret
    # requirement. See DEPLOYMENT.md.
    demo_secret: str | None = None

    # Freshness thresholds — demo-compressed (Phase 4). A production
    # deployment against real intraday/EOD equity data would reasonably use
    # minutes-scale thresholds (ARCHITECTURE.md's original 15s/2min/10min
    # figures); these are shortened specifically so live fault-injection is
    # demonstrable within a 5-minute presentation. All freshness-state code
    # reads these — no hardcoded values anywhere else.
    freshness_live_seconds: float = 5
    freshness_recent_seconds: float = 15
    freshness_delayed_seconds: float = 30
    freshness_stale_seconds: float = 30

    # Workstream 3: opt-in, additive-only second provider (LiveDelayedNSEProvider).
    # Orthogonal to demo_mode/fault injection — never enabled by default, never
    # wired into scoring. See PRODUCT.md's "Data source" section.
    live_provider_enabled: bool = False

    scheduler_interval_seconds: float = 5
    # Test-only escape hatch: the provider is always constructed (digest/
    # status endpoints need it), but the live background job is skippable
    # so the test suite isn't racing a real 5s-interval scheduler against
    # its own assertions. True in every real run (default + .env.example).
    scheduler_enabled: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
