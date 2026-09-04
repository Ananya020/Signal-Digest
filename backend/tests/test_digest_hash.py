import hashlib
import json

from app.services.digest import EMPTY_DIGEST_HASH, compute_aggregate_hash


def test_same_set_produces_identical_hash():
    a = compute_aggregate_hash([(1, 1), (2, 2)])
    b = compute_aggregate_hash([(1, 1), (2, 2)])
    assert a == b


def test_ordering_does_not_affect_hash():
    a = compute_aggregate_hash([(1, 1), (2, 2), (3, 3)])
    b = compute_aggregate_hash([(3, 3), (1, 1), (2, 2)])
    assert a == b


def test_removing_a_flag_changes_hash():
    full = compute_aggregate_hash([(1, 1), (2, 2)])
    reduced = compute_aggregate_hash([(1, 1)])
    assert full != reduced


def test_changing_severity_rank_changes_hash():
    a = compute_aggregate_hash([(1, 1)])
    b = compute_aggregate_hash([(1, 2)])
    assert a != b


def test_empty_set_has_stable_defined_hash():
    assert compute_aggregate_hash([]) == EMPTY_DIGEST_HASH
    # Independently reproducible per the documented canonical scheme, not
    # just internally consistent with itself.
    expected = hashlib.sha256(json.dumps([], separators=(",", ":")).encode("utf-8")).hexdigest()
    assert EMPTY_DIGEST_HASH == expected


def test_canonical_serialization_matches_documented_scheme():
    # flag_id=5, severity_rank=2 and flag_id=1, severity_rank=3 -> sorted by
    # flag_id ascending -> [[1,3],[5,2]]
    result = compute_aggregate_hash([(5, 2), (1, 3)])
    expected_serialized = json.dumps([[1, 3], [5, 2]], separators=(",", ":"))
    expected = hashlib.sha256(expected_serialized.encode("utf-8")).hexdigest()
    assert result == expected


def test_unrelated_watchlists_flags_do_not_affect_hash():
    # Simulated at the unit level: hash is a pure function of the pairs
    # passed in, so a watchlist's flags never influence another's — the
    # join itself (which flags belong to which watchlist) is what
    # guarantees this at the DB level, covered by an integration test.
    watchlist_a = compute_aggregate_hash([(1, 1), (2, 2)])
    watchlist_b_with_extra_unrelated_flag = compute_aggregate_hash([(1, 1), (2, 2), (99, 3)])
    assert watchlist_a != watchlist_b_with_extra_unrelated_flag  # different sets, as expected
    # But recomputing watchlist_a's own set again, regardless of what else
    # exists elsewhere, is unaffected:
    assert compute_aggregate_hash([(1, 1), (2, 2)]) == watchlist_a
