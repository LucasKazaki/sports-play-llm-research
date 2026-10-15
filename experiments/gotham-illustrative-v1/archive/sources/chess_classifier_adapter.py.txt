"""Audited data adapter for pinned ROOK-CLF-9m; never imports remote code.

Representation/action order: jorahn/rook@49b49aee5d6608f24f9be1f5436c6945238f9909
src/utils/common.py, src/model.py, src/const.py and their tests (MIT).
Model metadata: jrahn/ROOK-CLF-9m@a02db44faf1c495a85f9dd725584d197c58294a1.
Use stock transformers.LlamaForSequenceClassification outside this module.
"""
from __future__ import annotations

import ast
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Mapping, Sequence

import chess

MODEL_REVISION = "a02db44faf1c495a85f9dd725584d197c58294a1"
UPSTREAM_REVISION = "49b49aee5d6608f24f9be1f5436c6945238f9909"
NATIVE_CHARACTERS = "-.0123456789BKNPQRabcdefghknpqrw"
SPECIAL_IDS = {"[SEP]": 32, "[PAD]": 33, "[CLS]": 34, "[MASK]": 35}
ACTION_SPACE_SHA256 = "b3017e2ea6a41bc986a377880bcf69fff85cc03f6c4532debc311a6bf9a09494"


class AdapterInputError(ValueError):
    """The caller must retain this failed/unsupported case in its denominator."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


class AdapterContractError(ValueError):
    pass


def native_vocab() -> dict[str, int]:
    return {**{char: i for i, char in enumerate(NATIVE_CHARACTERS)}, **SPECIAL_IDS}


@lru_cache(maxsize=1)
def expected_action_space() -> tuple[str, ...]:
    """Reconstruct the upstream sorted 1968-class orthodox UCI action set."""
    moves = []
    for file in range(8):
        for rank in range(8):
            for target_file in range(8):
                for target_rank in range(8):
                    dx, dy = abs(file - target_file), abs(rank - target_rank)
                    if (dx or dy) and (dx == 0 or dy == 0 or dx == dy or (dx, dy) in ((1, 2), (2, 1))):
                        moves.append(f"{chr(97+file)}{rank+1}{chr(97+target_file)}{target_rank+1}")
            if rank in (1, 6):
                for target_file in range(max(0, file-1), min(7, file+1)+1):
                    for promotion in "bnqr":
                        moves.append(f"{chr(97+file)}{rank+1}{chr(97+target_file)}{1 if rank == 1 else 8}{promotion}")
    result = tuple(sorted(moves))
    checksum = hashlib.sha256(json.dumps(result, separators=(",", ":")).encode()).hexdigest()
    if len(result) != 1968 or checksum != ACTION_SPACE_SHA256:
        raise AdapterContractError("reconstructed action order differs from audited upstream")
    return result


def validate_vocab(vocab: Mapping[str, int]) -> dict[str, int]:
    expected = native_vocab()
    if not isinstance(vocab, Mapping) or dict(vocab) != expected or any(type(i) is not int for i in vocab.values()):
        raise AdapterContractError("native 32-character and four-special-token IDs must match exactly")
    return dict(vocab)


def verify_model_mapping(config: Mapping) -> tuple[str, ...]:
    """Reject reordered/missing classes and incompatible pooling/input IDs."""
    if not isinstance(config, Mapping):
        raise AdapterContractError("model config must be a mapping")
    expected = expected_action_space()
    id2label = config.get("id2label")
    if not isinstance(id2label, Mapping) or len(id2label) != 1968:
        raise AdapterContractError("id2label must contain exactly 1968 classes")
    normalized = {}
    for key, label in id2label.items():
        if type(key) is int:
            index = key
        elif type(key) is str and re.fullmatch(r"0|[1-9][0-9]*", key):
            index = int(key)
        else:
            raise AdapterContractError("class indices must be ordinary canonical integers")
        if index in normalized or type(label) is not str:
            raise AdapterContractError("duplicate or malformed class index/label")
        normalized[index] = label
    if normalized != dict(enumerate(expected)):
        raise AdapterContractError("id2label differs from pinned upstream UCI class order")
    inverse = config.get("label2id")
    if not isinstance(inverse, Mapping) or dict(inverse) != {move: i for i, move in enumerate(expected)} or any(type(i) is not int for i in inverse.values()):
        raise AdapterContractError("label2id must be the exact inverse of id2label")
    required = {"model_type": "llama", "architectures": ["LlamaForSequenceClassification"],
                "max_position_embeddings": 78, "vocab_size": 128,
                "pad_token_id": 33, "bos_token_id": 1, "eos_token_id": 2}
    for key, value in required.items():
        if config.get(key) != value or type(config.get(key)) is not type(value):
            raise AdapterContractError(f"incompatible native model setting: {key}")
    if "num_labels" in config and (type(config["num_labels"]) is not int or config["num_labels"] != 1968):
        raise AdapterContractError("num_labels must be 1968")
    return expected


def _json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise AdapterContractError(f"duplicate metadata key: {key}")
        value[key] = item
    return value


def _read_json(path: Path):
    if path.stat().st_size > 2_000_000:
        raise AdapterContractError("metadata file exceeds bounded reader")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_object)


def load_native_contract(model_dir: Path | str) -> dict:
    """Read JSON/literal metadata only; remote tokenizer/model modules never run.

    A partial local acquisition may omit tokenizer.json. Its tokenizer.py VOCAB
    and ACTION_SPACE literals are parsed with ast.literal_eval, then compared
    with the independently reconstructed contract. When tokenizer.json exists,
    its character BPE and added-token IDs must also agree.
    """
    root = Path(model_dir)
    config = _read_json(root / "config.json")
    labels = verify_model_mapping(config)
    metadata = _read_json(root / "tokenizer_config.json")
    if metadata.get("model_max_length") != 78 or type(metadata.get("model_max_length")) is not int:
        raise AdapterContractError("tokenizer context must be 78")
    for name, text in (("sep_token", "[SEP]"), ("pad_token", "[PAD]"), ("cls_token", "[CLS]"), ("mask_token", "[MASK]")):
        if metadata.get(name) != text:
            raise AdapterContractError(f"incorrect tokenizer {name}")
    added = metadata.get("added_tokens_decoder", {})
    if type(added) is not dict or set(added) != {str(i) for i in SPECIAL_IDS.values()} or any(type(added[str(i)]) is not dict or added[str(i)].get("content") != token or added[str(i)].get("special") is not True for token, i in SPECIAL_IDS.items()):
        raise AdapterContractError("tokenizer added special IDs differ from pinned metadata")
    paths = [root / "config.json", root / "tokenizer_config.json"]
    python_metadata = root / "tokenizer.py"
    if python_metadata.exists():
        if python_metadata.stat().st_size > 200_000:
            raise AdapterContractError("literal tokenizer metadata exceeds bound")
        literals = {}
        for node in ast.parse(python_metadata.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ("VOCAB", "ACTION_SPACE"):
                        if target.id in literals:
                            raise AdapterContractError("duplicate tokenizer literal")
                        literals[target.id] = ast.literal_eval(node.value)
        if literals.get("VOCAB") != list(NATIVE_CHARACTERS) or literals.get("ACTION_SPACE") != list(labels):
            raise AdapterContractError("local tokenizer literals differ from audited upstream")
        paths.append(python_metadata)
    token_json = root / "tokenizer.json"
    if token_json.exists():
        value = _read_json(token_json)
        model = value.get("model", {})
        if model.get("type") != "BPE" or model.get("vocab") != {c: i for i, c in enumerate(NATIVE_CHARACTERS)} or model.get("merges") != []:
            raise AdapterContractError("tokenizer JSON is not the native character BPE")
        if any(value.get(k) is not None for k in ("normalizer", "pre_tokenizer", "post_processor")):
            raise AdapterContractError("tokenizer JSON adds an unsupported text transform")
        tokens = value.get("added_tokens", [])
        if type(tokens) is not list or len(tokens) != 4 or any(type(item) is not dict or item.get("special") is not True or type(item.get("id")) is not int for item in tokens):
            raise AdapterContractError("tokenizer JSON added tokens differ")
        actual = {item.get("content"): item.get("id") for item in tokens}
        if actual != SPECIAL_IDS:
            raise AdapterContractError("tokenizer JSON special IDs differ")
        paths.append(token_json)
    if not python_metadata.exists() and not token_json.exists():
        raise AdapterContractError("tokenizer JSON or auditable literal metadata required")
    return {"vocab": native_vocab(), "id2label": labels, "label2id": {move: i for i, move in enumerate(labels)},
            "input_length": 78, "cls_token_id": 34, "pad_token_id": 33,
            "model_revision": MODEL_REVISION, "upstream_revision": UPSTREAM_REVISION,
            "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


def _validated_board(fen: str) -> chess.Board:
    if type(fen) is not str or len(fen) > 256 or len(fen.split(" ")) != 6 or any(not field for field in fen.split(" ")):
        raise AdapterInputError("invalid_fen", "six fields separated by single ASCII spaces are required")
    position, turn, castling, ep, halfmove, fullmove = fen.split(" ")
    if not re.fullmatch(r"[prnbqkPRNBQK1-8/]+", position) or turn not in ("w", "b"):
        raise AdapterInputError("invalid_fen", "orthodox piece placement and side to move required")
    if castling != "-" and not re.fullmatch(r"K?Q?k?q?", castling):
        raise AdapterInputError("unsupported_castling", "only standard KQkq castling notation is supported")
    if not re.fullmatch(r"-|[a-h][36]", ep):
        raise AdapterInputError("invalid_fen", "invalid en passant field")
    if not re.fullmatch(r"0|[1-9][0-9]*", halfmove) or not re.fullmatch(r"[1-9][0-9]*", fullmove):
        raise AdapterInputError("invalid_fen_counter", "canonical nonnegative halfmove and positive fullmove required")
    if len(halfmove) > 2:
        raise AdapterInputError("unsupported_halfmove_width", "native representation supports halfmove 0..99")
    if len(fullmove) > 3:
        raise AdapterInputError("unsupported_fullmove_width", "native representation supports fullmove 1..999")
    try:
        board = chess.Board(fen, chess960=False)
    except ValueError as exc:
        raise AdapterInputError("invalid_fen", "board parser rejected the position") from exc
    if not board.is_valid() or board.board_fen() != position:
        raise AdapterInputError("invalid_fen", "position is not a valid orthodox board with canonical ranks")
    return board


def native_text_for_fen(fen: str) -> str:
    """Return exactly 77 characters; preserve the supplied valid EP field."""
    _validated_board(fen)
    position, turn, castling, ep, halfmove, fullmove = fen.split(" ")
    squares = "".join("." * int(char) if char.isdigit() else char for char in position if char != "/")
    result = squares + turn + castling.ljust(4, ".") + ep.ljust(2, ".") + halfmove.ljust(2, ".") + "." + fullmove.ljust(3, ".")
    if len(result) != 77:
        raise AdapterInputError("unsupported_native_width", "no truncation or extra padding is permitted")
    return result


def token_ids_for_fen(fen: str, vocab: Mapping[str, int]) -> list[int]:
    mapping = validate_vocab(vocab)
    text = native_text_for_fen(fen)
    return [mapping[char] for char in text] + [mapping["[CLS]"]]


def encode_fen(fen: str, contract: Mapping) -> dict[str, list[int]]:
    """Tensor-free model input; caller may batch and tensorize without padding."""
    ids = token_ids_for_fen(fen, contract["vocab"])
    return {"input_ids": ids, "attention_mask": [1] * 78}


def rank_logits(fen: str, logits: Sequence[float], id2label: Sequence[str], top_k: int = 5) -> dict:
    """Return raw and legal-filtered rankings with original logits separately.

    No score is called an engine evaluation or probability. Ties use the lower
    upstream class index. Terminal valid boards keep a raw ranking and an
    explicitly empty legal ranking. Unsupported inputs raise AdapterInputError;
    callers must retain those failures in their original selected denominator.
    """
    board = _validated_board(fen)
    if not isinstance(id2label, Sequence) or isinstance(id2label, (str, bytes)) or tuple(id2label) != expected_action_space():
        raise AdapterContractError("ranking requires the verified exact class order")
    if type(top_k) is not int or not 1 <= top_k <= 1968:
        raise AdapterInputError("invalid_top_k", "top_k must be an integer in 1..1968")
    if not isinstance(logits, Sequence) or isinstance(logits, (str, bytes)) or len(logits) != 1968:
        raise AdapterInputError("invalid_logits", "exactly 1968 logits are required")
    if any(type(value) not in (int, float) for value in logits):
        raise AdapterInputError("invalid_logits", "use ordinary numeric logits, e.g. tensor.detach().cpu().tolist()")
    try:
        values = [float(value) for value in logits]
    except (ValueError, OverflowError) as exc:
        raise AdapterInputError("invalid_logits", "unrepresentable logit") from exc
    if not all(math.isfinite(value) for value in values):
        raise AdapterInputError("nonfinite_logits", "all logits must be finite")
    legal = {move.uci() for move in board.legal_moves}
    missing = legal - set(id2label)
    if missing:
        raise AdapterContractError("legal orthodox move is missing from action space")
    order = sorted(range(1968), key=lambda i: (-values[i], i))
    record = lambda i: {"class_id": i, "move_uci": id2label[i], "logit": values[i], "legal": id2label[i] in legal}
    raw = [record(i) for i in order[:top_k]]
    masked = [record(i) for i in order if id2label[i] in legal][:top_k]
    return {"status": "ok" if legal else "no_legal_moves", "score_type": "logit",
            "raw_topk": raw, "legal_topk": masked, "legal_move_count": len(legal),
            "raw_choice_uci": raw[0]["move_uci"], "raw_choice_is_legal": raw[0]["legal"],
            "legal_choice_uci": masked[0]["move_uci"] if masked else None}
