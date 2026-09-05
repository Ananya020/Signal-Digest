"""Today's Brief — deterministic template synthesis over already-scored
flags. No LLM, no network call, pure aggregation + string templates. Tests
cover: each template branch, the six computed facts' correctness,
determinism (same facts -> same text, always, regardless of input order),
and that zero signals renders nothing.
"""

from app.services.brief import build_brief, compute_brief_facts, render_brief


def _flag(ticker, severity, z_score, sector=None, sector_relative=None):
    return {"ticker": ticker, "severity": severity, "z_score": z_score, "sector": sector, "sector_relative": sector_relative}


# --- compute_brief_facts: the six deterministic facts ----------------------


def test_facts_zero_signals():
    facts = compute_brief_facts([])
    assert facts.total == 0
    assert facts.strongest is None
    assert facts.concentrated_sector is None
    assert facts.up_count == 0 and facts.down_count == 0


def test_facts_counts_by_severity_and_sector():
    flags = [
        _flag("HDFCBANK.NS", "notable", 2.1, sector="Banking/Finance"),
        _flag("ICICIBANK.NS", "significant", 2.9, sector="Banking/Finance"),
        _flag("ITC.NS", "extreme", -3.6, sector="Consumer/FMCG"),
    ]
    facts = compute_brief_facts(flags)
    assert facts.total == 3
    assert facts.severity_counts == {"notable": 1, "significant": 1, "extreme": 1}
    assert facts.sector_counts == {"Banking/Finance": 2, "Consumer/FMCG": 1}
    assert facts.concentrated_sector == "Banking/Finance"  # only sector with >= 2


def test_facts_no_sector_reaches_concentration_threshold():
    flags = [_flag("A.NS", "notable", 2.1, sector="X"), _flag("B.NS", "notable", 2.2, sector="Y")]
    facts = compute_brief_facts(flags)
    assert facts.concentrated_sector is None


def test_facts_two_flags_for_the_same_ticker_do_not_count_as_concentration():
    """Concentration is about distinct INSTRUMENTS, not flag rows — two
    flags for the same ticker (e.g. two different trading days both still
    active) must not read as "two companies in this sector moved.\""""
    flags = [
        _flag("ASIANPAINT.NS", "significant", 2.7, sector="Consumer/FMCG"),
        _flag("ASIANPAINT.NS", "notable", 2.3, sector="Consumer/FMCG"),
    ]
    facts = compute_brief_facts(flags)
    assert facts.sector_counts == {"Consumer/FMCG": 1}  # one distinct ticker, not two flag rows
    assert facts.concentrated_sector is None


def test_render_two_flags_same_ticker_same_sector_uses_neutral_branch_not_concentrated():
    flags = [
        _flag("ASIANPAINT.NS", "significant", 2.7, sector="Consumer/FMCG"),
        _flag("ASIANPAINT.NS", "notable", 2.3, sector="Consumer/FMCG"),
    ]
    facts = compute_brief_facts(flags)
    text = render_brief(facts)
    assert "concentrated" not in text.lower()
    # Must NOT claim "across different sectors" either — there's only one
    # sector here, just the same ticker twice.
    assert "different sectors" not in text.lower()
    assert text == "Two signals today; ASIANPAINT's move is the most extreme, at 2.7σ."


def test_facts_strongest_signal_is_the_largest_absolute_z():
    flags = [
        _flag("A.NS", "notable", 2.1, sector="X"),
        _flag("B.NS", "extreme", -4.3, sector="Y"),
        _flag("C.NS", "significant", 2.9, sector="Z"),
    ]
    facts = compute_brief_facts(flags)
    assert facts.strongest.ticker == "B.NS"
    assert facts.strongest.z_score == -4.3


def test_facts_strongest_tie_break_is_deterministic_by_ticker():
    flags = [_flag("Z.NS", "notable", 3.0), _flag("A.NS", "notable", -3.0)]
    facts = compute_brief_facts(flags)
    assert facts.strongest.ticker == "A.NS"  # identical |z|, alphabetically-first ticker wins, always


def test_facts_direction_breakdown():
    flags = [_flag("A.NS", "notable", 2.1), _flag("B.NS", "notable", -2.2), _flag("C.NS", "notable", 3.0)]
    facts = compute_brief_facts(flags)
    assert facts.up_count == 2
    assert facts.down_count == 1


def test_facts_missing_sector_excluded_not_guessed():
    flags = [_flag("A.NS", "notable", 2.1, sector=None), _flag("B.NS", "notable", 2.2, sector=None)]
    facts = compute_brief_facts(flags)
    assert facts.sector_counts == {}
    assert facts.concentrated_sector is None


# --- render_brief: template branches ---------------------------------------


def test_render_zero_signals_is_none_not_an_empty_string():
    assert render_brief(compute_brief_facts([])) is None


def test_render_single_signal_branch():
    facts = compute_brief_facts([_flag("HDFCBANK.NS", "significant", 2.8, sector="Banking/Finance")])
    assert render_brief(facts) == "HDFCBANK is the one signal that stands out today, moving 2.8σ outside its normal range."


def test_render_single_signal_branch_uses_absolute_zscore_for_a_negative_move():
    facts = compute_brief_facts([_flag("HDFCBANK.NS", "significant", -2.8, sector="Banking/Finance")])
    assert render_brief(facts) == "HDFCBANK is the one signal that stands out today, moving 2.8σ outside its normal range."


def test_render_concentrated_sector_branch():
    flags = [
        _flag("HDFCBANK.NS", "extreme", 4.1, sector="Banking/Finance"),
        _flag("ICICIBANK.NS", "notable", 2.1, sector="Banking/Finance"),
        _flag("AXISBANK.NS", "notable", -2.3, sector="Banking/Finance"),
    ]
    facts = compute_brief_facts(flags)
    assert render_brief(facts) == (
        "Three unusual moves today, concentrated in Banking/Finance — HDFCBANK is the most statistically unusual, "
        "including one extreme-severity move."
    )


def test_render_spread_across_sectors_branch():
    flags = [
        _flag("ITC.NS", "extreme", 3.6, sector="Consumer/FMCG"),
        _flag("HDFCBANK.NS", "notable", 2.1, sector="Banking/Finance"),
        _flag("MARUTI.NS", "notable", -2.2, sector="Auto"),
        _flag("NTPC.NS", "significant", 2.5, sector="Energy/Materials"),
    ]
    facts = compute_brief_facts(flags)
    assert render_brief(facts) == (
        "Four signals today across different sectors; ITC's move is the most extreme, at 3.6σ, "
        "including one extreme-severity move."
    )


def test_render_omits_extreme_clause_when_none_are_extreme():
    flags = [
        _flag("A.NS", "notable", 2.1, sector="X"),
        _flag("B.NS", "significant", -2.9, sector="Y"),
    ]
    facts = compute_brief_facts(flags)
    text = render_brief(facts)
    assert "extreme-severity" not in text.lower()  # "most extreme" (the base template wording) is unrelated to this clause
    assert text.endswith("2.9σ.")


def test_render_extreme_clause_pluralizes_correctly_for_multiple_extremes():
    flags = [
        _flag("A.NS", "extreme", 4.0, sector="X"),
        _flag("B.NS", "extreme", -4.1, sector="Y"),
        _flag("C.NS", "notable", 2.1, sector="Z"),
    ]
    facts = compute_brief_facts(flags)
    assert render_brief(facts).endswith("including two extreme-severity moves.")


def test_render_never_pads_in_extreme_clause_when_everything_is_notable():
    flags = [_flag("A.NS", "notable", 2.1, sector="X"), _flag("B.NS", "notable", 2.2, sector="Y"), _flag("C.NS", "notable", -2.3, sector="Z")]
    facts = compute_brief_facts(flags)
    assert "extreme-severity" not in render_brief(facts).lower()


def test_render_never_states_a_causal_reason_or_trading_claim():
    flags = [_flag("A.NS", "extreme", 4.0, sector="X"), _flag("B.NS", "notable", 2.1, sector="Y")]
    text = render_brief(compute_brief_facts(flags)).lower()
    for banned in ("because", "buy", "sell", "hold", "target", "expect", "predict", "should"):
        assert banned not in text


# --- determinism -------------------------------------------------------


def test_identical_facts_always_produce_identical_text():
    flags = [_flag("A.NS", "extreme", 4.0, sector="X"), _flag("B.NS", "notable", 2.1, sector="Y")]
    first = build_brief(flags)
    second = build_brief(flags)
    assert first == second


def test_output_is_independent_of_input_list_order():
    flags_a = [_flag("A.NS", "extreme", 4.0, sector="X"), _flag("B.NS", "notable", 2.1, sector="Y")]
    flags_b = list(reversed(flags_a))
    assert build_brief(flags_a) == build_brief(flags_b)


def test_build_brief_is_the_composition_of_facts_and_render():
    flags = [_flag("HDFCBANK.NS", "notable", 2.5, sector="Banking/Finance")]
    assert build_brief(flags) == render_brief(compute_brief_facts(flags))
