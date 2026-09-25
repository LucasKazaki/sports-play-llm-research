"""Fail-closed validator for a rights-bound Chess Concept seed manifest.
It validates local manifest structure only; it neither acquires a source nor proves
legal move replay.
"""
from datetime import datetime
import re
try:
    from .chess_concept_schema_validator import _basic_board_state, _fen
except ImportError:
    from chess_concept_schema_validator import _basic_board_state, _fen

ITEM_FIELDS = (
    "position_id", "game_id", "split", "source_url", "license", "rights_status",
    "retrieved_at", "source_bytes_sha256", "fen", "move_uci", "move_context",
    "transition_sha256", "legal_replay_hash",
)

def _sha(value):
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value)))

def _timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False

def _item_errors(item):
    errors = []
    if not isinstance(item, dict):
        return ["item_must_be_object"]
    for key in ITEM_FIELDS:
        if key not in item:
            errors.append("missing:" + key)
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", str(item.get("position_id", ""))):
        errors.append("invalid_position_id")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", str(item.get("game_id", ""))):
        errors.append("invalid_game_id")
    if item.get("split") not in {"train", "dev", "test"}:
        errors.append("invalid_split")
    if not re.fullmatch(r"https://[^\s]+", str(item.get("source_url", ""))):
        errors.append("invalid_source_url")
    if item.get("license") != "CC0-1.0" or item.get("rights_status") != "verified":
        errors.append("unverified_source_rights")
    if not _timestamp(item.get("retrieved_at")):
        errors.append("invalid_retrieval_timestamp")
    for key in ("source_bytes_sha256", "transition_sha256", "legal_replay_hash"):
        if not _sha(item.get(key)):
            errors.append("invalid:" + key)
    fen = item.get("fen", "")
    if not _fen(fen):
        errors.append("invalid_fen_syntax")
    elif not _basic_board_state(fen):
        errors.append("invalid_fen_board_state")
    if not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", str(item.get("move_uci", ""))):
        errors.append("invalid_move_uci")
    if not isinstance(item.get("move_context"), str) or not item["move_context"].strip():
        errors.append("invalid_move_context")
    return errors

def validate_seed_manifest(document):
    if not isinstance(document, dict):
        return {"valid": False, "errors": ["manifest_must_be_object"]}
    errors = []
    if document.get("schema_version") != "chessconcept-seed-manifest/v1":
        errors.append("unsupported_schema")
    items = document.get("items")
    if not isinstance(items, list):
        return {"valid": False, "errors": errors + ["items_must_be_list"]}
    if not 1 <= len(items) <= 24:
        errors.append("item_count_out_of_bounds")
    position_transitions, transition_hashes, position_ids, game_splits = set(), set(), set(), {}
    for index, item in enumerate(items):
        prefix = "item[%d]:" % index
        errors.extend(prefix + error for error in _item_errors(item))
        if not isinstance(item, dict):
            continue
        position_id = item.get("position_id")
        if position_id in position_ids:
            errors.append(prefix + "duplicate_position_id")
        position_ids.add(position_id)
        position_transition = (item.get("fen"), item.get("move_uci"))
        if position_transition in position_transitions:
            errors.append(prefix + "duplicate_position_transition")
        position_transitions.add(position_transition)
        transition_hash = item.get("transition_sha256")
        if transition_hash in transition_hashes:
            errors.append(prefix + "duplicate_transition_sha256")
        transition_hashes.add(transition_hash)
        game, split = item.get("game_id"), item.get("split")
        if game in game_splits and game_splits[game] != split:
            errors.append(prefix + "game_split_leakage:" + str(game))
        game_splits[game] = split
    return {"valid": not errors, "errors": errors}
