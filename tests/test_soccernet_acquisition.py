from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

from acquire_soccernet_sample import credential_from_texts, require_private_data_root


def test_credential_extraction_requires_password_context() -> None:
    assert credential_from_texts(['Access password is "demo1234".']) == "demo1234"


def test_credential_extraction_rejects_missing_candidate() -> None:
    with pytest.raises(ValueError, match="0 unambiguous"):
        credential_from_texts(["No authorization token is shown here."])


def test_credential_extraction_rejects_ambiguous_candidates() -> None:
    with pytest.raises(ValueError, match="2 unambiguous"):
        credential_from_texts(['password is "demo1234"', 'password is "other5678"'])


def test_download_destination_must_be_private(tmp_path: Path) -> None:
    accepted = tmp_path / "data" / "private" / "soccernet"
    assert require_private_data_root(accepted) == accepted.resolve()
    with pytest.raises(ValueError, match="data/private"):
        require_private_data_root(tmp_path / "artifacts" / "soccernet")
