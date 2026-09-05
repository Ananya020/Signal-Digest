"""Step B (Event Grouping) — pure unit tests over compute_events(), no DB
needed: it's a read-time aggregation purely over already-fetched rows."""

from app.services.digest import compute_events


def make_row(ticker, sector, z_score, sector_relative="sector_wide"):
    return {"ticker": ticker, "sector": sector, "z_score": z_score, "sector_relative": sector_relative}


def test_two_or_more_sector_wide_flags_in_the_same_sector_form_an_event():
    rows = [
        make_row("A.NS", "Energy", 2.5),
        make_row("B.NS", "Energy", -3.1),
    ]
    events = compute_events(rows)
    assert len(events) == 1
    assert events[0]["sector"] == "Energy"
    assert events[0]["tickers"] == ["A.NS", "B.NS"]
    assert events[0]["strongest_z_score"] == 3.1


def test_a_single_member_sector_is_not_an_event():
    rows = [make_row("A.NS", "Energy", 2.5)]
    assert compute_events(rows) == []


def test_stock_specific_flags_are_never_grouped_even_with_two_in_the_same_sector():
    rows = [
        make_row("A.NS", "Energy", 2.5, sector_relative="stock_specific"),
        make_row("B.NS", "Energy", -3.1, sector_relative="stock_specific"),
    ]
    assert compute_events(rows) == []


def test_multiple_sectors_each_with_2plus_members_produce_multiple_events_strongest_first():
    rows = [
        make_row("A.NS", "Energy", 2.0),
        make_row("B.NS", "Energy", 2.2),
        make_row("C.NS", "Auto", 4.5),
        make_row("D.NS", "Auto", -4.9),
    ]
    events = compute_events(rows)
    assert [e["sector"] for e in events] == ["Auto", "Energy"]
    assert events[0]["strongest_z_score"] == 4.9
    assert events[1]["strongest_z_score"] == 2.2


def test_mixed_sector_wide_and_stock_specific_only_groups_the_sector_wide_ones():
    rows = [
        make_row("A.NS", "Energy", 2.0, sector_relative="sector_wide"),
        make_row("B.NS", "Energy", 2.2, sector_relative="sector_wide"),
        make_row("C.NS", "Energy", 9.9, sector_relative="stock_specific"),
    ]
    events = compute_events(rows)
    assert len(events) == 1
    assert events[0]["tickers"] == ["A.NS", "B.NS"]
    assert events[0]["strongest_z_score"] == 2.2  # the stock-specific 9.9 is excluded
