#!/usr/bin/env python3
"""Select and verify the frozen harder chess cohort from retained CC0 bytes.

This evaluator-side command never calls a model or engine. It prints aggregate
counts only; source rows, themes, solutions and heldout FENs stay in local files.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re

import zstandard

import chess_harder_cohort_protocol_v2 as contract
import chess_real_data


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'artifacts/chess-harder-cohort-protocol-v2/20260928-operator-freeze/protocol.json'
BASE = ROOT / 'data/open/chess/lichess-real-seed-v1/manifest.json'
SOURCE = ROOT / 'data/open/chess/lichess-harder-v2-prefix-20260929'
MAX_DECOMPRESSED = 64 * 1024 * 1024
ALGORITHM = 'sha256-ranked-theme-first-rating-fill-split-v2'


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8') + b'\n'


def load_protocol() -> dict:
    protocol = json.loads(PROTOCOL.read_bytes())
    contract.validate_protocol(protocol, BASE)
    return protocol


def load_source(protocol: dict) -> tuple[dict, list[dict]]:
    receipt_raw = (SOURCE / 'acquisition-receipt.json').read_bytes()
    receipt = json.loads(receipt_raw)
    if receipt.get('schema') != 'project-public-data-acquisition/v1' \
            or receipt.get('source') != 'lichess-puzzle-prefix' \
            or receipt.get('synthetic') is not False or receipt.get('fullArchive') is not False \
            or receipt.get('license', {}).get('spdx') != 'CC0-1.0' \
            or receipt.get('prefix', {}).get('url') != contract.LICHESS_PUZZLE_URL \
            or receipt.get('page', {}).get('url') != contract.LICHESS_RIGHTS_URL:
        raise ValueError('retained_source_contract_changed')
    page = (SOURCE / 'source-page.html').read_bytes()
    compressed = (SOURCE / 'puzzles.csv.zst.part').read_bytes()
    for value, metadata in ((page, receipt['page']), (compressed, receipt['prefix'])):
        if len(value) != metadata['bytes'] or digest(value) != metadata['sha256']:
            raise ValueError('retained_source_bytes_changed')
    if len(compressed) > protocol['source']['max_additional_compressed_bytes'] \
            or receipt['prefix'].get('status') != 206 \
            or receipt['page'].get('status') != 200:
        raise ValueError('retained_source_bounds_invalid')
    content_range = receipt['prefix'].get('headers', {}).get('contentRange', '')
    match = re.fullmatch(r'bytes 0-(\d+)/(\d+)', content_range)
    if not match or int(match[1]) != len(compressed) - 1 \
            or int(match[2]) <= len(compressed):
        raise ValueError('retained_prefix_range_invalid')
    if b'cc0' not in page.lower() or b'lichess_db_puzzle.csv.zst' not in page:
        raise ValueError('retained_source_rights_missing')
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(compressed)) as stream:
        decoded = stream.read(MAX_DECOMPRESSED + 1)
    if len(decoded) > MAX_DECOMPRESSED or b'\n' not in decoded:
        raise ValueError('retained_prefix_decode_out_of_bounds')
    complete = decoded[:decoded.rfind(b'\n') + 1].decode('utf-8')
    reader = csv.DictReader(io.StringIO(complete))
    if not reader.fieldnames or not {'PuzzleId', 'FEN', 'Moves', 'Rating', 'Themes', 'GameUrl'} \
            <= set(reader.fieldnames):
        raise ValueError('retained_prefix_columns_invalid')
    rows = []
    seen_positions = set()
    for source_row in reader:
        item = chess_real_data.derive_row(source_row)
        if item['position_id'] in seen_positions:
            raise ValueError('retained_prefix_duplicate_position')
        seen_positions.add(item['position_id'])
        rows.append(item)
    if not rows:
        raise ValueError('retained_prefix_no_complete_rows')
    acquisition = {
        'canonical_url': protocol['source']['canonical_url'],
        'rights_url': protocol['source']['rights_url'],
        'license': protocol['source']['license'],
        'retrieved_at': receipt['retrievedAt'],
        'source_page_sha256': receipt['page']['sha256'],
        'prefix_sha256': receipt['prefix']['sha256'],
        'compressed_bytes': len(compressed),
        'full_archive': False,
    }
    return acquisition, rows


def choose(protocol: dict, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    exclusions = contract._base_exclusions(BASE, protocol['exclusion']['v1_manifest_sha256'])
    strata = protocol['cohort']['rating_strata']
    themes = protocol['cohort']['theme_strata']
    protocol_hash = contract.sha256_json(protocol)
    candidates = []
    for row in rows:
        if any(row[key] in exclusions[key] for key in exclusions):
            continue
        band = next((stratum['id'] for stratum in strata
                     if stratum['minimum'] <= row['rating'] <= stratum['maximum']), None)
        if band is None:
            continue
        candidates.append({'row': row, 'band': band, 'rank': digest(
            f'{protocol_hash}:{row["position_id"]}'.encode('ascii'))})
    candidates.sort(key=lambda item: (item['rank'], item['row']['position_id']))
    selected = []
    seen = {key: set() for key in exclusions}
    band_counts = {stratum['id']: 0 for stratum in strata}
    theme_counts = {stratum['theme']: 0 for stratum in themes}

    def can_take(candidate: dict) -> bool:
        row = candidate['row']
        quota = next(stratum['positions'] for stratum in strata if stratum['id'] == candidate['band'])
        return band_counts[candidate['band']] < quota and all(
            row[key] not in seen[key] for key in seen)

    def take(candidate: dict) -> None:
        selected.append(candidate)
        band_counts[candidate['band']] += 1
        for key in seen:
            seen[key].add(candidate['row'][key])
        for theme in theme_counts:
            theme_counts[theme] += theme in candidate['row']['themes']

    for theme in themes:
        while theme_counts[theme['theme']] < theme['minimum_positions']:
            candidate = next((entry for entry in candidates
                              if theme['theme'] in entry['row']['themes'] and can_take(entry)), None)
            if candidate is None:
                raise ValueError('retained_prefix_cannot_fill_theme_strata')
            take(candidate)
    for candidate in candidates:
        if len(selected) == protocol['cohort']['target_positions']:
            break
        if can_take(candidate):
            take(candidate)
    if len(selected) != protocol['cohort']['target_positions'] \
            or any(band_counts[stratum['id']] != stratum['positions'] for stratum in strata):
        raise ValueError('retained_prefix_cannot_fill_rating_strata')
    ordered_games = sorted((entry['row']['game_id'] for entry in selected),
                           key=lambda game: (digest(f'{protocol_hash}:split:{game}'.encode('ascii')), game))
    split_by_game = {}
    offset = 0
    for split in ('train', 'dev', 'heldout'):
        count = protocol['split']['counts'][split]
        split_by_game.update({game: split for game in ordered_games[offset:offset + count]})
        offset += count
    items, entries = [], []
    for selected_row in selected:
        row = selected_row['row']
        items.append({
            'position_id': row['position_id'], 'game_id': row['game_id'],
            'source_fen': row['source_fen'], 'fen': row['fen'],
            'setup_move': row['setup_move'],
            'legal_replay': [{'before': row['source_fen'], 'uci': row['setup_move'],
                              'after': row['fen']}],
            'split': split_by_game[row['game_id']],
        })
        entries.append({'position_id': row['position_id'], 'rating': row['rating'],
                        'themes': sorted(theme for theme in theme_counts if theme in row['themes'])})
    return items, entries


def expected(protocol: dict) -> tuple[dict, list[dict], list[dict], int]:
    acquisition, rows = load_source(protocol)
    items, entries = choose(protocol, rows)
    return acquisition, items, entries, len(rows)


def redacted_result(protocol: dict, manifest: dict, audit: dict,
                    acquisition: dict, items: list[dict], entries: list[dict],
                    row_count: int) -> dict:
    if manifest['acquisition'] != acquisition or manifest['items'] != items \
            or audit['entries'] != entries:
        raise ValueError('cohort_differs_from_retained_source_selection')
    result = contract.validate_staged_manifest(protocol, manifest, audit, BASE)
    return {'schema': 'chess-harder-prefix-selection-validation/v2',
            'algorithm': ALGORITHM, 'protocol_sha256': result['protocol_sha256'],
            'cohort_manifest_sha256': result['cohort_manifest_sha256'],
            'strata_audit_sha256': result['strata_audit_sha256'],
            'source_complete_rows': row_count, 'item_count': result['item_count'],
            'split_counts': result['split_counts'], 'legal_replay_passed': True,
            'source_row_binding_passed': True, 'base_exclusion_passed': True,
            'strata_audit_passed': True, 'heldout_outcomes_scored': 0,
            'model_calls': 0, 'engine_calls': 0, 'commentary_gate_passed': False}


def build(output: Path) -> dict:
    if output.exists():
        raise ValueError('cohort_output_exists_use_new_version')
    protocol = load_protocol()
    acquisition, items, entries, row_count = expected(protocol)
    manifest = {'schema': contract.COHORT_SCHEMA,
                'protocol_sha256': contract.sha256_json(protocol),
                'acquisition': acquisition, 'strata_audit_sha256': '0' * 64,
                'items': items}
    audit = {'schema': contract.STRATA_AUDIT_SCHEMA,
             'protocol_sha256': contract.sha256_json(protocol),
             'cohort_payload_sha256': contract.sha256_json(contract._staged_manifest_payload(manifest)),
             'sealed_at': datetime.now(timezone.utc).isoformat(),
             'exposure': 'evaluator-only', 'entries': entries}
    manifest['strata_audit_sha256'] = contract.sha256_json(audit)
    result = redacted_result(protocol, manifest, audit, acquisition, items, entries, row_count)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'manifest.json').write_bytes(json_bytes(manifest))
    (output / 'evaluator-only-strata-audit.json').write_bytes(json_bytes(audit))
    (output / 'validation.json').write_bytes(json_bytes(result))
    return result


def verify(output: Path) -> dict:
    protocol = load_protocol()
    acquisition, items, entries, row_count = expected(protocol)
    manifest = json.loads((output / 'manifest.json').read_bytes())
    audit = json.loads((output / 'evaluator-only-strata-audit.json').read_bytes())
    result = redacted_result(protocol, manifest, audit, acquisition, items, entries, row_count)
    if (output / 'validation.json').read_bytes() != json_bytes(result):
        raise ValueError('cohort_validation_receipt_changed')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    result = build(args.output_dir) if args.command == 'build' else verify(args.output_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
