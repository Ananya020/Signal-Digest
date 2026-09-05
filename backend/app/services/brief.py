""""Today's Brief" — a short, deterministic synthesis of the current
unacknowledged digest signals. NO LLM, NO external call, NO network
dependency of any kind: pure aggregation over the exact flag rows
`GET /digest` already fetches, then fixed string templates. Same input
facts always produce the exact same output text — there is nothing here
that could vary between calls (no clock reads, no randomness, no external
state beyond the flags list itself).

This is the "deterministic template is the default target" position
PRODUCT.md already staked out for the one-line per-flag explanation
(`frontend/lib/explain.ts`) — this brief is the same idea one level up
(across all active flags, not one). It is NOT the optional LLM-phrasing
layer PRODUCT.md separately scopes as a possible future addition; that
remains distinct, unbuilt, and would only ever touch phrasing of an
already-computed structured fact, same as this — never decision logic,
never scoring, never ranking. Read-only, presentation-layer only: nothing
here writes to `flags`, `flag_ack`, or influences severity/rank/ack-bust in
any way — it runs strictly *after* the digest has already been computed.

## Style, reused deliberately from explain.ts

Magnitude/statistical fact only, never causal narrative ("fell because...")
and never a trading/investment claim (buy/sell/hold/target/prediction) —
same guardrail `explain.ts` already follows for the per-flag line.
"""

from dataclasses import dataclass
from typing import Iterable, Mapping

_COUNT_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


def _count_word(n: int, *, capitalize: bool = False) -> str:
    word = _COUNT_WORDS.get(n, str(n))
    return word.capitalize() if capitalize and word.isalpha() else word


def _bare_ticker(ticker: str) -> str:
    return ticker[:-3] if ticker.endswith(".NS") else ticker


@dataclass(frozen=True)
class StrongestSignal:
    ticker: str
    severity: str
    z_score: float
    sector_relative: str | None


@dataclass(frozen=True)
class BriefFacts:
    """All six deterministic facts the brief is built from — every one of
    them already derivable from the digest's own flag rows; nothing here
    queries price_ticks/baselines directly."""

    total: int
    severity_counts: Mapping[str, int]
    sector_counts: Mapping[str, int]  # distinct TICKERS per sector, not flag rows — see compute_brief_facts
    concentrated_sector: str | None  # a sector with >=2 distinct tickers flagged, if any (highest count wins; alphabetical tie-break)
    strongest: StrongestSignal | None
    up_count: int
    down_count: int


def compute_brief_facts(flags: Iterable[Mapping]) -> BriefFacts:
    """`flags` items need only provide `ticker`, `severity`, `z_score`,
    and optionally `sector`/`sector_relative` (missing/None sector values
    are simply excluded from `sector_counts` — never guessed at)."""
    flags = list(flags)
    total = len(flags)

    severity_counts: dict[str, int] = {}
    sector_tickers: dict[str, set[str]] = {}
    up_count = 0
    down_count = 0

    for f in flags:
        severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1
        sector = f.get("sector")
        if sector:
            # "Concentration" is about how many distinct INSTRUMENTS are
            # unusual in a sector, not how many flag rows exist — two flags
            # for the same ticker (e.g. two different trading days) must
            # never read as "two companies in this sector moved."
            sector_tickers.setdefault(sector, set()).add(f["ticker"])
        z = f["z_score"] or 0
        if z >= 0:
            up_count += 1
        else:
            down_count += 1

    sector_counts = {sector: len(tickers) for sector, tickers in sector_tickers.items()}

    concentrated_candidates = sorted(
        ((count, sector) for sector, count in sector_counts.items() if count >= 2),
        key=lambda pair: (-pair[0], pair[1]),  # highest count first, alphabetical tie-break — deterministic regardless of input order
    )
    concentrated_sector = concentrated_candidates[0][1] if concentrated_candidates else None

    strongest = None
    if flags:
        # Highest |z_score| wins; ticker (ascending) is the tie-break, so
        # the choice is deterministic even across two flags with an
        # identical |z_score| — independent of whatever order the caller's
        # list happens to be in. `min` over (-|z|, ticker) picks the largest
        # |z| first, then the alphabetically-first ticker on a tie.
        top = min(flags, key=lambda f: (-abs(f["z_score"] or 0), f["ticker"]))
        strongest = StrongestSignal(
            ticker=top["ticker"],
            severity=top["severity"],
            z_score=top["z_score"] or 0,
            sector_relative=top.get("sector_relative"),
        )

    return BriefFacts(
        total=total,
        severity_counts=severity_counts,
        sector_counts=sector_counts,
        concentrated_sector=concentrated_sector,
        strongest=strongest,
        up_count=up_count,
        down_count=down_count,
    )


def render_brief(facts: BriefFacts) -> str | None:
    """Pure template synthesis — same facts in, same sentence out, always.
    Zero signals renders nothing (the existing calm empty-state copy is the
    caller's job to show instead, never an empty/awkward brief string)."""
    if facts.total == 0 or facts.strongest is None:
        return None

    strongest_ticker = _bare_ticker(facts.strongest.ticker)
    strongest_z = abs(facts.strongest.z_score)
    extreme_count = facts.severity_counts.get("extreme", 0)

    if facts.total == 1:
        return f"{strongest_ticker} is the one signal that stands out today, moving {strongest_z:.1f}σ outside its normal range."

    count_word = _count_word(facts.total, capitalize=True)

    if facts.concentrated_sector:
        sentence = (
            f"{count_word} unusual move{'s' if facts.total != 1 else ''} today, concentrated in "
            f"{facts.concentrated_sector} — {strongest_ticker} is the most statistically unusual"
        )
    elif len(facts.sector_counts) >= 2:
        # Genuinely spread across multiple distinct sectors — the claim in
        # the sentence below is actually true.
        sentence = (
            f"{count_word} signals today across different sectors; "
            f"{strongest_ticker}'s move is the most extreme, at {strongest_z:.1f}σ"
        )
    else:
        # Not concentrated (no sector has >=2 distinct tickers) but also not
        # spread across multiple sectors — e.g. two flags for the same
        # ticker, or sector data unavailable. Never claim "across different
        # sectors" when that isn't actually true.
        sentence = f"{count_word} signals today; {strongest_ticker}'s move is the most extreme, at {strongest_z:.1f}σ"

    if extreme_count > 0:
        return f"{sentence}, including {_count_word(extreme_count)} extreme-severity move{'s' if extreme_count != 1 else ''}."
    return f"{sentence}."


def build_brief(flags: Iterable[Mapping]) -> str | None:
    """Convenience: `render_brief(compute_brief_facts(flags))` in one call —
    what `GET /digest` actually uses."""
    return render_brief(compute_brief_facts(flags))
