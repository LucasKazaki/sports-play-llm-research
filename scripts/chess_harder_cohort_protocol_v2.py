"""Offline validation for a separately versioned, no-forward chess cohort protocol.

This module deliberately does not acquire data, call an engine, or call a model.
It keeps the historical ``chess-real-seed/v1`` importer frozen while making the
next cohort's preconditions machine-checkable before any acquisition is allowed.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import chess


PROTOCOL_SCHEMA = "chess-harder-cohort-protocol/v2"
COHORT_SCHEMA = "chess-harder-cohort-manifest/v2"
STRATA_AUDIT_SCHEMA = "chess-harder-cohort-strata-audit/v2"
VALIDATION_SCHEMA = "chess-harder-cohort-validation/v2"
BASE_SCHEMA = "chess-real-seed/v1"
MAX_POSITIONS = 240
MAX_ADDITIONAL_COMPRESSED_BYTES = 8 * 1024 * 1024
LICHESS_PUZZLE_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
LICHESS_RIGHTS_URL = "https://database.lichess.org/"
FORBIDDEN_GENERATOR_FIELDS = (
    "engine_pv",
    "evaluator_material",
    "future_moves",
    "post_move_fen",
    "solution",
    "solution_uci",
    "target_move",
    "themes",
    "annotations",
    "answer_labels",
)


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_json(value):
    return sha256_bytes(_json_bytes(value))


def _fail(code):
    raise ValueError(code)


def _object(value, code):
    if not isinstance(value, dict):
        _fail(code)
    return value


def _exact_keys(value, expected, code):
    value = _object(value, code)
    if set(value) != set(expected):
        _fail(code)
    return value


def _sha256(value, code):
    if not isinstance(value, str) or len(value) != 64:
        _fail(code)
    try:
        int(value, 16)
    except ValueError:
        _fail(code)
    return value.lower()


def _positive_int(value, code):
    if type(value) is not int or value <= 0:
        _fail(code)
    return value


def _timestamp(value, code):
    if not isinstance(value, str):
        _fail(code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail(code)
    if parsed.tzinfo is None:
        _fail(code)
    return parsed


def _distinct_strings(values, code, allow_empty=False):
    if not isinstance(values, list) or (not allow_empty and not values) \
            or any(not isinstance(item, str) or not item for item in values):
        _fail(code)
    if len(values) != len(set(values)):
        _fail(code)
    return values


def _validate_protocol_shape(protocol):
    protocol = _exact_keys(protocol, {
        "schema", "protocol_id", "frozen_at", "source", "cohort", "split",
        "exclusion", "generator_contract", "outcome_accounting",
    }, "protocol_keys_invalid")
    if protocol["schema"] != PROTOCOL_SCHEMA or not isinstance(protocol["protocol_id"], str) \
            or not protocol["protocol_id"].strip():
        _fail("protocol_identity_invalid")
    _timestamp(protocol["frozen_at"], "protocol_frozen_at_invalid")

    source = _exact_keys(protocol["source"], {
        "canonical_url", "rights_url", "license", "hash_algorithm",
        "max_additional_compressed_bytes", "full_archive",
    }, "protocol_source_invalid")
    if source["canonical_url"] != LICHESS_PUZZLE_URL or source["rights_url"] != LICHESS_RIGHTS_URL \
            or source["license"] != "CC0-1.0" or source["hash_algorithm"] != "sha256" \
            or source["full_archive"] is not False:
        _fail("protocol_source_invalid")
    if type(source["max_additional_compressed_bytes"]) is not int \
            or not 0 < source["max_additional_compressed_bytes"] <= MAX_ADDITIONAL_COMPRESSED_BYTES:
        _fail("protocol_compressed_budget_invalid")

    cohort = _exact_keys(protocol["cohort"], {"target_positions", "rating_strata", "theme_strata"},
                         "protocol_cohort_invalid")
    target_positions = _positive_int(cohort["target_positions"], "protocol_target_positions_invalid")
    if target_positions > MAX_POSITIONS:
        _fail("protocol_target_positions_invalid")
    rating = cohort["rating_strata"]
    if not isinstance(rating, list) or not rating:
        _fail("protocol_rating_strata_invalid")
    rating_ids, rating_ranges, rating_total = set(), [], 0
    for stratum in rating:
        stratum = _exact_keys(stratum, {"id", "minimum", "maximum", "positions"},
                              "protocol_rating_strata_invalid")
        identifier = stratum["id"]
        if not isinstance(identifier, str) or not identifier or identifier in rating_ids \
                or type(stratum["minimum"]) is not int or type(stratum["maximum"]) is not int \
                or stratum["minimum"] < 0 or stratum["maximum"] < stratum["minimum"]:
            _fail("protocol_rating_strata_invalid")
        rating_ids.add(identifier)
        rating_ranges.append((stratum["minimum"], stratum["maximum"]))
        rating_total += _positive_int(stratum["positions"], "protocol_rating_strata_invalid")
    if rating_total != target_positions:
        _fail("protocol_rating_strata_do_not_cover_target")
    for index, (minimum, maximum) in enumerate(rating_ranges):
        for other_minimum, other_maximum in rating_ranges[index + 1:]:
            if minimum <= other_maximum and other_minimum <= maximum:
                _fail("protocol_rating_strata_overlap")
    themes = cohort["theme_strata"]
    if not isinstance(themes, list) or not themes:
        _fail("protocol_theme_strata_invalid")
    theme_ids = set()
    for stratum in themes:
        stratum = _exact_keys(stratum, {"theme", "minimum_positions"}, "protocol_theme_strata_invalid")
        theme = stratum["theme"]
        if not isinstance(theme, str) or not theme or theme in theme_ids:
            _fail("protocol_theme_strata_invalid")
        theme_ids.add(theme)
        if _positive_int(stratum["minimum_positions"], "protocol_theme_strata_invalid") > target_positions:
            _fail("protocol_theme_strata_invalid")

    split = _exact_keys(protocol["split"], {"game_disjoint", "counts", "heldout_sealed"},
                        "protocol_split_invalid")
    counts = _exact_keys(split["counts"], {"train", "dev", "heldout"}, "protocol_split_invalid")
    if split["game_disjoint"] is not True or split["heldout_sealed"] is not True \
            or sum(_positive_int(counts[name], "protocol_split_invalid") for name in counts) != target_positions:
        _fail("protocol_split_invalid")

    exclusion = _exact_keys(protocol["exclusion"], {"v1_manifest_sha256"}, "protocol_exclusion_invalid")
    _sha256(exclusion["v1_manifest_sha256"], "protocol_exclusion_invalid")

    generator = _exact_keys(protocol["generator_contract"], {"allowed_fields", "forbidden_fields"},
                            "protocol_generator_contract_invalid")
    if generator["allowed_fields"] != ["fen"] \
            or set(_distinct_strings(generator["forbidden_fields"], "protocol_generator_contract_invalid")) \
            != set(FORBIDDEN_GENERATOR_FIELDS):
        _fail("protocol_generator_contract_invalid")

    accounting = _exact_keys(protocol["outcome_accounting"], {
        "raw_outputs_retained", "abstentions_retained", "legal_replay_required",
        "independent_evaluation_required", "no_engine_or_model_before_freeze",
    }, "protocol_outcome_accounting_invalid")
    if any(accounting[name] is not True for name in accounting):
        _fail("protocol_outcome_accounting_invalid")
    return protocol


def _base_exclusions(path, expected_hash):
    path = Path(path)
    raw = path.read_bytes()
    if sha256_bytes(raw) != _sha256(expected_hash, "protocol_exclusion_invalid"):
        _fail("base_manifest_hash_mismatch")
    try:
        base = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("base_manifest_invalid")
    if not isinstance(base, dict) or base.get("schema") != BASE_SCHEMA or not isinstance(base.get("items"), list):
        _fail("base_manifest_invalid")
    keys = {"game_id": set(), "position_id": set(), "source_fen": set(), "fen": set()}
    for item in base["items"]:
        if not isinstance(item, dict):
            _fail("base_manifest_invalid")
        for key in keys:
            value = item.get(key)
            if not isinstance(value, str) or not value:
                _fail("base_manifest_invalid")
            keys[key].add(value)
    return keys


def validate_protocol(protocol, base_manifest_path):
    """Validate the pre-acquisition protocol without exposing source rows or labels."""
    protocol = _validate_protocol_shape(protocol)
    _base_exclusions(base_manifest_path, protocol["exclusion"]["v1_manifest_sha256"])
    return {
        "schema": VALIDATION_SCHEMA,
        "protocol_sha256": sha256_json(protocol),
        "target_positions": protocol["cohort"]["target_positions"],
        "split_counts": protocol["split"]["counts"],
        "max_additional_compressed_bytes": protocol["source"]["max_additional_compressed_bytes"],
        "base_manifest_sha256": protocol["exclusion"]["v1_manifest_sha256"],
        "generator_input_fields": ["fen"],
        "gate_flags": {
            "acquisition_completed": False,
            "commentary_capability_passed": False,
            "heldout_evaluated": False,
        },
    }


def _replay_item(item):
    item = _exact_keys(item, {
        "position_id", "game_id", "source_fen", "fen", "setup_move", "legal_replay", "split",
    }, "cohort_item_invalid")
    for key in ("position_id", "game_id", "source_fen", "fen", "setup_move"):
        if not isinstance(item[key], str) or not item[key]:
            _fail("cohort_item_invalid")
    if item["split"] not in {"train", "dev", "heldout"}:
        _fail("cohort_item_invalid")
    if not isinstance(item["legal_replay"], list) or len(item["legal_replay"]) != 1:
        _fail("cohort_replay_must_not_include_future_moves")
    step = _exact_keys(item["legal_replay"][0], {"before", "uci", "after"}, "cohort_replay_invalid")
    if step["before"] != item["source_fen"] or step["uci"] != item["setup_move"] or step["after"] != item["fen"]:
        _fail("cohort_replay_binding_invalid")
    try:
        board = chess.Board(item["source_fen"])
        move = chess.Move.from_uci(item["setup_move"])
    except ValueError:
        _fail("cohort_replay_invalid")
    if not board.is_valid() or move not in board.legal_moves:
        _fail("cohort_replay_invalid")
    board.push(move)
    if board.fen() != item["fen"]:
        _fail("cohort_replay_binding_invalid")
    return item


def _staged_manifest_payload(manifest):
    """Return the cohort content committed by an evaluator-only sidecar.

    The sidecar digest itself is intentionally excluded to avoid a circular
    hash.  All source rows and acquisition metadata remain covered.
    """
    return {
        "schema": manifest["schema"],
        "protocol_sha256": manifest["protocol_sha256"],
        "acquisition": manifest["acquisition"],
        "items": manifest["items"],
    }


def _validate_strata_audit(audit, manifest, protocol, position_ids, retrieved_at, frozen_at, observed_at):
    """Validate a manifest-committed evaluator-only audit without returning rows."""
    audit = _exact_keys(audit, {
        "schema", "protocol_sha256", "cohort_payload_sha256", "sealed_at", "exposure", "entries",
    }, "cohort_strata_audit_invalid")
    if audit["schema"] != STRATA_AUDIT_SCHEMA or audit["exposure"] != "evaluator-only":
        _fail("cohort_strata_audit_invalid")
    if _sha256(audit["protocol_sha256"], "cohort_strata_audit_invalid") != sha256_json(protocol):
        _fail("cohort_strata_audit_protocol_binding_invalid")
    if _sha256(audit["cohort_payload_sha256"], "cohort_strata_audit_invalid") \
            != sha256_json(_staged_manifest_payload(manifest)):
        _fail("cohort_strata_audit_payload_binding_invalid")
    sealed_at = _timestamp(audit["sealed_at"], "cohort_strata_audit_invalid")
    if sealed_at <= retrieved_at or sealed_at <= frozen_at:
        _fail("cohort_strata_audit_not_sealed_after_acquisition")
    if sealed_at > observed_at:
        _fail("cohort_strata_audit_after_validation")
    if not isinstance(audit["entries"], list) or len(audit["entries"]) != len(position_ids):
        _fail("cohort_strata_audit_item_binding_invalid")

    rating_strata = protocol["cohort"]["rating_strata"]
    rating_counts = {stratum["id"]: 0 for stratum in rating_strata}
    theme_strata = protocol["cohort"]["theme_strata"]
    theme_counts = {stratum["theme"]: 0 for stratum in theme_strata}
    audit_ids = set()
    for entry in audit["entries"]:
        entry = _exact_keys(entry, {"position_id", "rating", "themes"}, "cohort_strata_audit_invalid")
        position_id = entry["position_id"]
        if not isinstance(position_id, str) or not position_id or position_id in audit_ids:
            _fail("cohort_strata_audit_item_binding_invalid")
        audit_ids.add(position_id)
        if type(entry["rating"]) is not int or entry["rating"] < 0:
            _fail("cohort_strata_rating_invalid")
        matches = [
            stratum["id"] for stratum in rating_strata
            if stratum["minimum"] <= entry["rating"] <= stratum["maximum"]
        ]
        if len(matches) != 1:
            _fail("cohort_strata_rating_invalid")
        rating_counts[matches[0]] += 1
        themes = _distinct_strings(entry["themes"], "cohort_strata_audit_invalid", allow_empty=True)
        if set(themes) - set(theme_counts):
            _fail("cohort_strata_theme_invalid")
        for theme in themes:
            theme_counts[theme] += 1
    if audit_ids != position_ids:
        _fail("cohort_strata_audit_item_binding_invalid")
    if any(rating_counts[stratum["id"]] != stratum["positions"] for stratum in rating_strata):
        _fail("cohort_rating_strata_counts_invalid")
    if any(theme_counts[stratum["theme"]] < stratum["minimum_positions"] for stratum in theme_strata):
        _fail("cohort_theme_strata_counts_invalid")
    audit_sha256 = sha256_json(audit)
    if _sha256(manifest["strata_audit_sha256"], "cohort_manifest_invalid") != audit_sha256:
        _fail("cohort_strata_audit_binding_invalid")
    return audit_sha256


def validate_staged_manifest(protocol, cohort_manifest, strata_audit, base_manifest_path):
    """Check an already-staged cohort and sealed evaluator-only strata locally.

    ``strata_audit`` is deliberately separate from the cohort rows and from any
    generator packet.  Its SHA-256 is committed in the manifest and its content
    commits the remaining manifest payload, preventing sidecar replacement.
    This validator emits only a hash-bound aggregate verdict, never the audit's
    ratings, theme memberships, or position identifiers.
    """
    validation = validate_protocol(protocol, base_manifest_path)
    observed_at = datetime.now(timezone.utc)
    manifest = _exact_keys(cohort_manifest, {
        "schema", "protocol_sha256", "acquisition", "strata_audit_sha256", "items",
    },
                           "cohort_manifest_invalid")
    if manifest["schema"] != COHORT_SCHEMA or manifest["protocol_sha256"] != validation["protocol_sha256"]:
        _fail("cohort_protocol_binding_invalid")
    acquisition = _exact_keys(manifest["acquisition"], {
        "canonical_url", "rights_url", "license", "retrieved_at", "source_page_sha256",
        "prefix_sha256", "compressed_bytes", "full_archive",
    }, "cohort_acquisition_invalid")
    source = protocol["source"]
    if acquisition["canonical_url"] != source["canonical_url"] or acquisition["rights_url"] != source["rights_url"] \
            or acquisition["license"] != source["license"] or acquisition["full_archive"] is not False:
        _fail("cohort_acquisition_invalid")
    retrieved_at = _timestamp(acquisition["retrieved_at"], "cohort_acquisition_invalid")
    frozen_at = _timestamp(protocol["frozen_at"], "protocol_frozen_at_invalid")
    if retrieved_at <= frozen_at:
        _fail("cohort_acquisition_precedes_protocol_freeze")
    if retrieved_at > observed_at:
        _fail("cohort_acquisition_after_validation")
    _sha256(acquisition["source_page_sha256"], "cohort_acquisition_invalid")
    _sha256(acquisition["prefix_sha256"], "cohort_acquisition_invalid")
    if type(acquisition["compressed_bytes"]) is not int or not 0 < acquisition["compressed_bytes"] \
            <= source["max_additional_compressed_bytes"]:
        _fail("cohort_acquisition_invalid")

    items = manifest["items"]
    if not isinstance(items, list) or len(items) != protocol["cohort"]["target_positions"]:
        _fail("cohort_item_count_invalid")
    exclusions = _base_exclusions(base_manifest_path, protocol["exclusion"]["v1_manifest_sha256"])
    seen = {key: set() for key in exclusions}
    split_counts = {"train": 0, "dev": 0, "heldout": 0}
    for raw_item in items:
        item = _replay_item(raw_item)
        for key in seen:
            value = item[key]
            if value in exclusions[key]:
                _fail("cohort_reuses_frozen_v1_position")
            if value in seen[key]:
                _fail("cohort_duplicates_internally")
            seen[key].add(value)
        split_counts[item["split"]] += 1
    if split_counts != protocol["split"]["counts"]:
        _fail("cohort_split_counts_invalid")
    strata_audit_sha256 = _validate_strata_audit(
        strata_audit, manifest, protocol, seen["position_id"], retrieved_at, frozen_at, observed_at,
    )
    return {
        "schema": VALIDATION_SCHEMA,
        "protocol_sha256": validation["protocol_sha256"],
        "cohort_manifest_sha256": sha256_json(manifest),
        "item_count": len(items),
        "split_counts": split_counts,
        "legal_replay_passed": True,
        "base_exclusion_passed": True,
        "strata_audit_sha256": strata_audit_sha256,
        "strata_audit_passed": True,
        "acquisition_after_protocol_freeze": True,
        "strata_audit_sealed_after_acquisition": True,
        "gate_flags": validation["gate_flags"],
    }


def write_protocol_summary(path, protocol, base_manifest_path):
    """Create one redacted pre-acquisition receipt; it never contains cohort rows."""
    path = Path(path)
    if path.exists():
        _fail("protocol_summary_exists")
    summary = validate_protocol(protocol, base_manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(summary) + b"\n")
    return summary


def write_staged_validation(path, protocol, cohort_manifest, strata_audit, base_manifest_path):
    """Create one immutable, redacted staged-validation receipt.

    Invoke this only through the native executor for a real staged cohort: the
    server-owned native receipt then supplies the external observation time for
    this create-only validation artifact.  It never writes source rows or audit
    entries to the result.
    """
    path = Path(path)
    if path.exists():
        _fail("staged_validation_exists")
    result = validate_staged_manifest(protocol, cohort_manifest, strata_audit, base_manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(result) + b"\n")
    return result
