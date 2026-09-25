"""Acquire one authorized SoccerNet game half without persisting its password.

The user-supplied authorization screenshot is OCR'd in memory.  Its credential is
never printed, written to disk, placed in a command line, or included in a receipt.
The official SoccerNet downloader is then restricted to one named game and a
small explicit file list.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import cv2


VIDEO_FILES = {"1_224p.mkv", "2_224p.mkv"}
ALLOWED_FILES = VIDEO_FILES | {"Labels-v2.json"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def credential_from_texts(texts: Iterable[str]) -> str:
    """Extract one credential near the word password, rejecting ambiguity."""
    joined = " ".join(str(text) for text in texts)
    patterns = (
        r"password.{0,100}?[\"'“”]\s*([A-Za-z0-9]{6,32})",
        r"password.{0,40}?(?:\bis\b|:)\s*[\"'“”]?\s*([A-Za-z0-9]{6,32})",
    )
    candidates: list[str] = []
    for pattern in patterns:
        candidates.extend(re.findall(pattern, joined, flags=re.IGNORECASE))
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise ValueError(f"authorization OCR produced {len(unique)} unambiguous credential candidates")
    return unique[0]


def _ocr_variants(image_path: Path) -> list[str]:
    from rapidocr_onnxruntime import RapidOCR

    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"could not decode authorization image: {image_path}")
    height, width = image.shape[:2]
    upper_body = image[int(height * 0.15):int(height * 0.45), :]
    gray = cv2.cvtColor(upper_body, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    thresholded = cv2.threshold(enlarged, 210, 255, cv2.THRESH_BINARY)[1]
    engine = RapidOCR()
    texts: list[str] = []
    for variant in (image, upper_body, enlarged, thresholded):
        result, _ = engine(variant)
        texts.extend(item[1] for item in (result or []))
    return texts


def authorization_password(image_path: Path) -> str:
    return credential_from_texts(_ocr_variants(image_path))


def redacted_ocr_diagnostic(image_path: Path) -> dict[str, object]:
    texts = _ocr_variants(image_path)
    try:
        credential = credential_from_texts(texts)
    except ValueError:
        credential = None
    return {
        "ocr_text_count": len(texts),
        "credential_pattern_found": credential is not None,
        "credential_length": None if credential is None else len(credential),
    }


def require_private_data_root(path: Path) -> Path:
    resolved = path.resolve()
    lowered = [part.lower() for part in resolved.parts]
    if not any(lowered[index:index + 2] == ["data", "private"] for index in range(len(lowered) - 1)):
        raise ValueError("SoccerNet media destination must be inside a data/private directory")
    return resolved


def resolve_game(split: str, game_index: int) -> str:
    from SoccerNet.utils import getListGames

    games = getListGames(split)
    if game_index < 0 or game_index >= len(games):
        raise IndexError(f"game index {game_index} outside {split} split of {len(games)} games")
    return games[game_index]


def acquire(
    *, authorization_image: Path, local_directory: Path, split: str,
    game_index: int, files: list[str], receipt_path: Path,
) -> dict[str, object]:
    invalid = sorted(set(files) - ALLOWED_FILES)
    if invalid:
        raise ValueError(f"files outside bounded allow-list: {invalid}")
    if not any(name in VIDEO_FILES for name in files):
        raise ValueError("at least one 224p video half is required")
    if "Labels-v2.json" not in files:
        raise ValueError("Labels-v2.json is required for evaluation")
    if not authorization_image.is_file():
        raise FileNotFoundError(authorization_image)
    local_directory = require_private_data_root(local_directory)

    game = resolve_game(split, game_index)
    password = authorization_password(authorization_image)
    import SoccerNet
    from SoccerNet.Downloader import SoccerNetDownloader

    downloader = SoccerNetDownloader(LocalDirectory=str(local_directory))
    downloader.password = password
    try:
        downloader.downloadGame(game=game, files=files, spl=split, verbose=True)
    finally:
        downloader.password = None
        password = ""

    game_directory = local_directory / Path(game)
    records: list[dict[str, object]] = []
    for name in files:
        path = game_directory / name
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"authorized download did not produce a non-empty file: {path}")
        records.append({
            "name": name,
            "relative_path": str(path.relative_to(local_directory)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    labels_path = game_directory / "Labels-v2.json"
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    annotations = labels.get("annotations")
    if not isinstance(annotations, list) or not annotations:
        raise RuntimeError("Labels-v2.json has no annotation records")

    receipt: dict[str, object] = {
        "schema_version": "playground-soccernet-acquisition-receipt-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "provider": "SoccerNet",
        "package_version": SoccerNet.__version__,
        "authorization": {
            "method": "user-provided NDA authorization email; credential OCR'd in memory",
            "credential_persisted": False,
            "redistribution_allowed": False,
            "intended_use": "non-commercial research and local demonstration",
        },
        "selection": {
            "split": split,
            "game_index": game_index,
            "game": game.replace("\\", "/"),
            "files": files,
        },
        "downloaded_files": records,
        "annotation_count": len(annotations),
    }
    write_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization-image", type=Path, required=True)
    parser.add_argument("--local-directory", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "valid", "test"), default="valid")
    parser.add_argument("--game-index", type=int, default=0)
    parser.add_argument("--files", nargs="+", default=["1_224p.mkv", "Labels-v2.json"])
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--check-authorization-only", action="store_true")
    args = parser.parse_args()
    if args.check_authorization_only:
        print(json.dumps(redacted_ocr_diagnostic(args.authorization_image), indent=2))
        return 0
    receipt = acquire(
        authorization_image=args.authorization_image,
        local_directory=args.local_directory,
        split=args.split,
        game_index=args.game_index,
        files=args.files,
        receipt_path=args.receipt,
    )
    print(json.dumps({
        "status": "downloaded_and_verified",
        "provider": receipt["provider"],
        "selection": receipt["selection"],
        "annotation_count": receipt["annotation_count"],
        "receipt": str(args.receipt),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
