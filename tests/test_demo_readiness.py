"""Regression cases where a healthy-looking demo cannot pass rehearsal."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototype"))
from demo_readiness import local_base, search_checks, status_checks


@pytest.mark.parametrize("url", ["https://example.com", "http://127.0.0.1.evil.test", "http://user:pass@localhost", "http://localhost/private", "http://localhost?x=1"])
def test_rehearsal_rejects_nonlocal_or_ambiguous_origin(url):
    with pytest.raises(ValueError):
        local_base(url)


def test_healthy_legacy_backend_does_not_pass_full_match_readiness():
    checks = status_checks({"key": "soccer", "available": True, "backend": "legacy_sqlite_fallback"})
    assert checks["soccer_available"]
    assert not checks["sealed_longform_backend"]
    assert not checks["all_96_windows_loaded"]
    assert not checks["performance_claims_blocked"]


def test_empty_or_misbound_results_do_not_pass_rehearsal():
    search = {"sport": "soccer", "result_count": 1, "results": [{"clip_url": "/media/football/clip", "relative_start_s": 2, "relative_end_s": 4}]}
    assert not search_checks(search, {})["all_results_have_valid_playback"]
    search["results"] = []
    assert not search_checks(search, {})["soccer_results_returned"]
    assert not search_checks(search, {})["count_matches_payload"]


def test_model_rehearsal_rejects_silent_fallback_and_invalid_timestamps():
    clips = {"/media/soccer/half-1": {"duration_s": 2700}}
    search = {"interpretation": {"source": "deterministic_literal_fallback", "error": "model unavailable"},
              "results": [{"clip_url": "/media/soccer/half-1", "relative_start_s": 2690, "relative_end_s": 2710}]}
    checks = search_checks(search, clips, require_local_model=True)
    assert not checks["query_execution_mode"]
    assert not checks["all_results_have_valid_playback"]
