"""Fail-closed structural gates for Chess Concept Model evidence packets.
This module validates provenance and evidence shape; it does not prove chess legality.
"""
import re

CONCEPTS = {"king_safety", "material", "development", "center", "piece_activity", "pawn_structure", "space", "tactical_threat", "endgame_transition"}
REQ = ("schema_version", "position_id", "game_id", "split", "fen", "move_uci", "source", "legal_board_verified", "engine_evidence", "commentary_evidence")

def _fen(value):
    try:
        board, side, castling, ep, half, full = value.split()
        ranks = board.split("/")
        return len(ranks) == 8 and all(re.fullmatch(r"[prnbqkPRNBQK1-8]+", r) and sum(int(c) if c.isdigit() else 1 for c in r) == 8 for r in ranks) and side in {"w", "b"} and (castling == "-" or re.fullmatch(r"[KQkq]+", castling)) and (ep == "-" or re.fullmatch(r"[a-h][36]", ep)) and int(half) >= 0 and int(full) > 0
    except (AttributeError, ValueError):
        return False

def _basic_board_state(value):
    try:
        ranks = value.split()[0].split("/")
        kings, pawns = {"w": [], "b": []}, {"w": 0, "b": 0}
        for rank_index, rank in enumerate(ranks):
            file_index = 0
            for cell in rank:
                if cell.isdigit():
                    file_index += int(cell); continue
                if cell == "K": kings["w"].append((rank_index, file_index))
                elif cell == "k": kings["b"].append((rank_index, file_index))
                elif cell == "P": pawns["w"] += 1
                elif cell == "p": pawns["b"] += 1
                if cell in "Pp" and rank_index in {0, 7}: return False
                file_index += 1
        if any(len(positions) != 1 for positions in kings.values()) or any(count > 8 for count in pawns.values()): return False
        white, black = kings["w"][0], kings["b"][0]
        return max(abs(white[0] - black[0]), abs(white[1] - black[1])) > 1
    except (AttributeError, IndexError, ValueError):
        return False

def validate_position(item):
    errors = []
    for key in REQ:
        if key not in item: errors.append("missing:" + key)
    if "legal_replay_hash" not in item: errors.append("missing:legal_replay_hash")
    elif not re.fullmatch(r"[0-9a-f]{64}", str(item["legal_replay_hash"])): errors.append("invalid_legal_replay_hash")
    if not _fen(item.get("fen", "")): errors.append("invalid_fen_syntax")
    elif not _basic_board_state(item["fen"]): errors.append("invalid_fen_board_state")
    if not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", str(item.get("move_uci", ""))): errors.append("invalid_move_uci")
    if item.get("schema_version") != "position-evidence/v1": errors.append("unsupported_schema")
    if item.get("split") not in {"train", "dev", "test"}: errors.append("invalid_split")
    if item.get("legal_board_verified") is not True: errors.append("legal_board_not_verified")
    source = item.get("source", {})
    if not isinstance(source, dict) or any(not isinstance(source.get(k), str) or not source[k].strip() for k in ("source_id", "game_ref", "license", "rights_status")): errors.append("invalid_source_provenance")
    elif source["license"] not in {"CC0-1.0", "public-domain-USA"} or source["rights_status"] != "verified": errors.append("unverified_source_rights")
    engine = item.get("engine_evidence", [])
    if not isinstance(engine, list) or len(engine) < 2: errors.append("engine_candidate_comparison_required")
    else:
        ids = set()
        for candidate in engine:
            if not isinstance(candidate, dict) or not re.fullmatch(r"[A-Za-z0-9._-]+", str(candidate.get("id", ""))) or not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", str(candidate.get("move_uci", ""))) or not isinstance(candidate.get("score_cp"), int): errors.append("invalid_engine_evidence"); break
            if candidate["id"] in ids: errors.append("duplicate_engine_evidence_id"); break
            ids.add(candidate["id"])
    commentary = item.get("commentary_evidence", [])
    if not isinstance(commentary, list) or any(not isinstance(v, dict) or not isinstance(v.get("id"), str) or not isinstance(v.get("source_ref"), str) for v in commentary): errors.append("invalid_commentary_evidence")
    return {"valid": not errors, "errors": errors}

def validate_explanation(item, explanation):
    errors = []
    abstain = explanation.get("abstain")
    if not isinstance(abstain, bool): errors.append("abstain_must_be_boolean")
    verdict = explanation.get("verdict")
    if verdict not in {"abstain", "concept_explanation"}: errors.append("invalid_verdict")
    elif isinstance(abstain, bool) and ((abstain and verdict != "abstain") or (not abstain and verdict != "concept_explanation")):
        errors.append("verdict_abstention_mismatch")
    confidence = explanation.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1: errors.append("invalid_confidence")
    concepts = explanation.get("concepts", [])
    if not isinstance(concepts, list) or any(v not in CONCEPTS for v in concepts): errors.append("invalid_concepts")
    engine_ids = {v.get("id") for v in item.get("engine_evidence", []) if isinstance(v, dict)}
    comment_ids = {v.get("id") for v in item.get("commentary_evidence", []) if isinstance(v, dict)}
    for key, allowed in (("engine_evidence_refs", engine_ids), ("commentary_evidence_refs", comment_ids)):
        refs = explanation.get(key, [])
        if not isinstance(refs, list) or any(v not in allowed for v in refs): errors.append("invalid_" + key)
    if not engine_ids and abstain is not True: errors.append("missing_engine_requires_abstention")
    if abstain is False:
        if not concepts or not explanation.get("engine_evidence_refs"): errors.append("claim_requires_concept_and_engine_evidence")
        if not isinstance(explanation.get("move_summary"), str) or not explanation["move_summary"].strip(): errors.append("missing_move_summary")
        primary = explanation.get("primary_concepts")
        if not isinstance(primary, list) or not primary or any(
            not isinstance(v, dict) or v.get("concept") not in CONCEPTS or
            not isinstance(v.get("claim"), str) or not v["claim"].strip() or
            not isinstance(v.get("evidence_refs"), list) or not v["evidence_refs"] or
            any(ref not in engine_ids for ref in v["evidence_refs"])
            for v in primary
        ): errors.append("invalid_primary_concepts")
        limitations = explanation.get("limitations")
        if not isinstance(limitations, list) or not limitations or any(not isinstance(v, str) or not v.strip() for v in limitations):
            errors.append("invalid_limitations")
    return {"valid": not errors, "errors": errors}

def validate_manifest(manifest):
    errors, positions, games = [], set(), {}
    items = manifest.get("items", []) if isinstance(manifest, dict) else []
    if not isinstance(items, list): return {"valid": False, "errors": ["items_must_be_list"]}
    for item in items:
        errors += ["%s:%s" % (item.get("position_id", "?"), e) for e in validate_position(item)["errors"]]
        signature = (item.get("fen"), item.get("move_uci"))
        if signature in positions: errors.append("duplicate_position_transition")
        positions.add(signature)
        game, split = item.get("game_id"), item.get("split")
        if game in games and games[game] != split: errors.append("game_split_leakage:" + str(game))
        games[game] = split
    return {"valid": not errors, "errors": errors}
