"""Freshness state classification — pure function of real elapsed wall-clock
time, per ARCHITECTURE.md. Four ascending thresholds define five states:

    age < live_seconds     -> LIVE
    age < recent_seconds    -> RECENT
    age < delayed_seconds   -> DELAYED
    age < stale_seconds     -> DELAYED (still delayed; the explicit STALE
                                cutoff hasn't been reached yet — this branch
                                only has effect if stale_seconds is
                                configured strictly greater than
                                delayed_seconds, e.g. production values where
                                DELAYED spans a wider window than the demo
                                defaults, which set them equal)
    otherwise               -> STALE

All four thresholds are configurable (see app/config.py) — no hardcoded
values here or anywhere else in freshness-state code.
"""


def classify_freshness(
    age_seconds: float,
    live_seconds: float,
    recent_seconds: float,
    delayed_seconds: float,
    stale_seconds: float,
) -> str:
    if age_seconds < live_seconds:
        return "LIVE"
    if age_seconds < recent_seconds:
        return "RECENT"
    if age_seconds < delayed_seconds:
        return "DELAYED"
    if age_seconds < stale_seconds:
        return "DELAYED"
    return "STALE"
