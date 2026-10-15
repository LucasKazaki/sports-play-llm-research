"""CPU-only representation/legality checks; never loads model weights."""
import hashlib
import json
from pathlib import Path
import random
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chess_classifier_adapter as adapter


def metadata_files(tmp_path):
    labels = adapter.expected_action_space()
    config = {"model_type": "llama", "architectures": ["LlamaForSequenceClassification"],
              "max_position_embeddings": 78, "vocab_size": 128,
              "pad_token_id": 33, "bos_token_id": 1, "eos_token_id": 2,
              "id2label": {str(i): move for i, move in enumerate(labels)},
              "label2id": {move: i for i, move in enumerate(labels)}}
    tok = {"model_max_length": 78, "sep_token": "[SEP]", "pad_token": "[PAD]",
           "cls_token": "[CLS]", "mask_token": "[MASK]",
           "added_tokens_decoder": {str(i): {"content": token, "special": True}
                                    for token, i in adapter.SPECIAL_IDS.items()}}
    (tmp_path / "config.json").write_text(json.dumps(config))
    (tmp_path / "tokenizer_config.json").write_text(json.dumps(tok))
    # A tokenizer import would fail. The loader must read only literal data.
    (tmp_path / "tokenizer.py").write_text(
        "raise AssertionError('remote module must never execute')\n"
        + f"VOCAB = {list(adapter.NATIVE_CHARACTERS)!r}\nACTION_SPACE = {list(labels)!r}\n")
    return config, tok


def test_action_order_matches_pinned_official_golden_checksum():
    labels = adapter.expected_action_space()
    assert len(labels) == len(set(labels)) == 1968
    assert hashlib.sha256(json.dumps(labels, separators=(",", ":")).encode()).hexdigest() == "b3017e2ea6a41bc986a377880bcf69fff85cc03f6c4532debc311a6bf9a09494"
    assert labels[:3] == ("a1a2", "a1a3", "a1a4")
    assert labels[-3:] == ("h8h5", "h8h6", "h8h7")
    for move in ("e1g1", "e1c1", "e8g8", "e8c8", "a7a8q", "a7a8n", "b2a1r", "h2h1b"):
        assert move in labels
    assert "a1a1" not in labels and "0000" not in labels


def test_official_process_fen_test_fixture_is_exact():
    fen = "1r6/p5k1/5p2/PPp3p1/2r3P1/4B3/4KP2/R7 w - - 1 33"
    expected = ".r......p.....k......p..PPp...p...r...P.....B.......KP..R.......w-...-.1..33."
    assert adapter.native_text_for_fen(fen) == expected
    ids = adapter.token_ids_for_fen(fen, adapter.native_vocab())
    assert len(expected) == 77 and len(ids) == 78 and ids[-1] == 34
    assert ids[:-1] == [adapter.native_vocab()[char] for char in expected]


def test_initial_position_has_native_pieces_turn_castling_ep_and_counter_fields():
    text = adapter.native_text_for_fen(chess.STARTING_FEN)
    assert text[:64] == "rnbqkbnrpppppppp" + "." * 32 + "PPPPPPPPRNBQKBNR"
    assert text[64:] == "wKQkq-.0..1.."
    encoded = adapter.encode_fen(chess.STARTING_FEN, {"vocab": adapter.native_vocab()})
    assert encoded["attention_mask"] == [1] * 78
    assert encoded["input_ids"][-1] == 34
    assert 33 not in encoded["input_ids"]  # dot padding is an ordinary token.


def test_valid_uncapturable_ep_target_is_preserved_not_silently_normalized():
    board = chess.Board()
    board.push_uci("e2e4")
    fen = board.fen(en_passant="fen")
    assert fen.split()[3] == "e3"
    assert adapter.native_text_for_fen(fen)[69:71] == "e3"


@pytest.mark.parametrize("half,full", [("0", "1"), ("9", "9"), ("10", "10"), ("99", "999")])
def test_supported_clock_width_boundaries(half, full):
    fen = " ".join(chess.STARTING_FEN.split()[:4] + [half, full])
    text = adapter.native_text_for_fen(fen)
    assert len(text) == 77
    assert text[71:74] == half.ljust(2, ".") + "."
    assert text[74:77] == full.ljust(3, ".")


@pytest.mark.parametrize("half,full,code", [("100", "1", "unsupported_halfmove_width"),
                                            ("0", "1000", "unsupported_fullmove_width"),
                                            ("-1", "1", "invalid_fen_counter"),
                                            ("00", "1", "invalid_fen_counter"),
                                            ("0", "0", "invalid_fen_counter")])
def test_counter_rejection_is_explicit_without_truncation(half, full, code):
    fen = " ".join(chess.STARTING_FEN.split()[:4] + [half, full])
    with pytest.raises(adapter.AdapterInputError) as failure:
        adapter.token_ids_for_fen(fen, adapter.native_vocab())
    assert failure.value.code == code


@pytest.mark.parametrize("fen", [None, "", chess.STARTING_FEN + " extra",
    chess.STARTING_FEN.replace(" w ", "  w "), chess.STARTING_FEN.replace("KQkq", "HAha"),
    chess.STARTING_FEN.replace(" w ", " x "), "8/8/8/8/8/8/8/8 w - - 0 1",
    chess.STARTING_FEN.replace("8/8/8/8", "11111111/8/8/8"),
    chess.STARTING_FEN.replace(" - 0 1", " e4 0 1")])
def test_invalid_or_nonorthodox_input_rejected(fen):
    with pytest.raises(adapter.AdapterInputError):
        adapter.native_text_for_fen(fen)


def test_loader_never_executes_remote_python_and_checks_inverse_maps(tmp_path):
    config, tok = metadata_files(tmp_path)
    contract = adapter.load_native_contract(tmp_path)
    assert contract["vocab"] == adapter.native_vocab()
    assert len(contract["id2label"]) == 1968
    assert contract["label2id"]["e1g1"] == contract["id2label"].index("e1g1")
    assert set(contract["source_sha256"]) == {"config.json", "tokenizer_config.json", "tokenizer.py"}
    config["label2id"]["e1g1"] = 0
    (tmp_path / "config.json").write_text(json.dumps(config))
    with pytest.raises(adapter.AdapterContractError, match="inverse"):
        adapter.load_native_contract(tmp_path)


@pytest.mark.parametrize("field,value", [("pad_token_id", 0), ("bos_token_id", 0),
    ("eos_token_id", 1), ("vocab_size", 36), ("max_position_embeddings", 77),
    ("architectures", ["LlamaForCausalLM"]), ("model_type", "gpt2")])
def test_incompatible_native_model_metadata_rejected(tmp_path, field, value):
    config, _ = metadata_files(tmp_path)
    config[field] = value
    with pytest.raises(adapter.AdapterContractError):
        adapter.verify_model_mapping(config)


def test_class_order_permutation_cannot_pass_even_with_consistent_inverse(tmp_path):
    config, _ = metadata_files(tmp_path)
    config["id2label"]["0"], config["id2label"]["1"] = config["id2label"]["1"], config["id2label"]["0"]
    config["label2id"] = {move: int(i) for i, move in config["id2label"].items()}
    with pytest.raises(adapter.AdapterContractError, match="class order"):
        adapter.verify_model_mapping(config)


def test_tokenizer_special_ids_and_literal_vocab_are_verified(tmp_path):
    _, tok = metadata_files(tmp_path)
    tok["added_tokens_decoder"]["34"]["content"] = "[BAD]"
    (tmp_path / "tokenizer_config.json").write_text(json.dumps(tok))
    with pytest.raises(adapter.AdapterContractError, match="special IDs"):
        adapter.load_native_contract(tmp_path)
    metadata_files(tmp_path)
    (tmp_path / "tokenizer.py").write_text("VOCAB = ['wrong']\nACTION_SPACE = []\n")
    with pytest.raises(adapter.AdapterContractError, match="literals"):
        adapter.load_native_contract(tmp_path)


def test_optional_tokenizer_json_must_preserve_character_bpe(tmp_path):
    metadata_files(tmp_path)
    token_json = {"model": {"type": "BPE", "vocab": {c: i for i, c in enumerate(adapter.NATIVE_CHARACTERS)}, "merges": []},
                  "normalizer": None, "pre_tokenizer": None, "post_processor": None,
                  "added_tokens": [{"content": token, "id": i, "special": True} for token, i in adapter.SPECIAL_IDS.items()]}
    (tmp_path / "tokenizer.json").write_text(json.dumps(token_json))
    assert "tokenizer.json" in adapter.load_native_contract(tmp_path)["source_sha256"]
    token_json["post_processor"] = {"type": "TemplateProcessing"}
    (tmp_path / "tokenizer.json").write_text(json.dumps(token_json))
    with pytest.raises(adapter.AdapterContractError, match="transform"):
        adapter.load_native_contract(tmp_path)


def test_raw_illegal_choice_is_retained_separately_from_masked_legal_choice():
    labels = adapter.expected_action_space()
    logits = [0.0] * 1968
    logits[labels.index("a1a8")] = 100.0
    logits[labels.index("e2e4")] = 99.0
    result = adapter.rank_logits(chess.STARTING_FEN, logits, labels, top_k=2)
    assert result["raw_choice_uci"] == "a1a8" and result["raw_choice_is_legal"] is False
    assert result["raw_topk"][0]["logit"] == 100.0
    assert result["legal_choice_uci"] == "e2e4"
    assert all(row["legal"] for row in result["legal_topk"])
    assert result["legal_move_count"] == 20


@pytest.mark.parametrize("fen,move", [("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"),
    ("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1", "e8c8"),
    ("7k/P7/8/8/8/8/8/7K w - - 0 1", "a7a8n"),
    ("7k/8/8/8/8/8/p7/7K b - - 0 1", "a2a1r"),
    ("7k/8/8/3pP3/8/8/8/7K w - d6 0 10", "e5d6")])
def test_legal_mask_understands_castling_underpromotion_and_ep(fen, move):
    labels = adapter.expected_action_space()
    logits = [0.0] * 1968
    logits[labels.index(move)] = 2.0
    result = adapter.rank_logits(fen, logits, labels)
    assert result["raw_choice_uci"] == result["legal_choice_uci"] == move


def test_terminal_position_keeps_raw_output_with_empty_legal_set():
    fen = "7k/6Q1/5K2/8/8/8/8/8 b - - 0 1"
    result = adapter.rank_logits(fen, [0.0] * 1968, adapter.expected_action_space())
    assert result["status"] == "no_legal_moves"
    assert result["raw_choice_uci"] is not None and result["raw_choice_is_legal"] is False
    assert result["legal_choice_uci"] is None and result["legal_topk"] == []


@pytest.mark.parametrize("logits", [None, "bad", [0.0] * 1967, [float("nan")] * 1968,
                                   [float("inf")] * 1968, [True] * 1968, ["0"] * 1968])
def test_malformed_or_nonfinite_logits_rejected(logits):
    with pytest.raises(adapter.AdapterInputError):
        adapter.rank_logits(chess.STARTING_FEN, logits, adapter.expected_action_space())


def test_legal_space_complete_on_finite_replayed_games():
    labels = adapter.expected_action_space()
    rng = random.Random(408)
    board = chess.Board()
    for _ in range(128):
        if board.is_game_over():
            board = chess.Board()
        assert {m.uci() for m in board.legal_moves} <= set(labels)
        if board.halfmove_clock <= 99 and board.fullmove_number <= 999:
            assert len(adapter.token_ids_for_fen(board.fen(en_passant="fen"), adapter.native_vocab())) == 78
        board.push(rng.choice(list(board.legal_moves)))
