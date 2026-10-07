"""First V12 partition: source-bound V11 prompt and frozen no-forward request.

This module only builds bytes. It has no transport, marker, evaluator, model or
engine call. A later create-only capture module must own denominator and raw
response accounting before any one-ply development trial can be dispatched.
"""
from __future__ import annotations

import json

import chess_counterfactual_evidence as cf
import chess_endgame_promotion_contrast_v11 as checker
import chess_no_forward_teaching_capture_v7 as capture_v7
import chess_no_forward_teaching_capture_v9 as capture_v9
import chess_no_forward_teaching_v7 as teaching_v7


SCHEMA = 'chess-promotion-one-ply-input/v12'
DECLARED_ROUTE = capture_v9.DECLARED_ROUTE
ROUTE_SHA256 = capture_v9.ROUTE_SHA256
MODEL_ID = 'loops-cpu-gpt-oss-20b'
ENDPOINT = 'http://127.0.0.1:1234/v1'


def build_request(packet_bytes: bytes, packet_sha256: str,
                  source_binding: dict) -> tuple[bytes, bytes]:
    """Return exact nine-field projection and the sole proposed request bytes.

    V11 verifies the source packet before any projection. V7 then validates
    every projected nested key and scalar leaf. The two temporary V7 version
    values used for that check are never sent to a model.
    """
    projection = checker.build_generator_input(
        packet_bytes, packet_sha256, source_binding=source_binding)
    if type(projection) is not bytes or not 0 < len(projection) <= 16_384:
        raise ValueError('v12_invalid_projection_bytes')
    try:
        value = capture_v7._strict_response_json(projection)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError('v12_invalid_projection_json') from error
    if (type(value) is not dict or
            set(value) != set(capture_v7.PROJECTION_FIELDS) or
            projection != cf.canonical(value) or
            value.get('schema') != checker.INPUT_SCHEMA or
            value.get('assertion_kinds') != [checker.KIND, 'abstention']):
        raise ValueError('v12_invalid_projection')
    _, route = capture_v9._route(DECLARED_ROUTE)
    if (cf.file_digest(DECLARED_ROUTE) != ROUTE_SHA256 or
            route['model_id'] != MODEL_ID or
            route['endpoint'] != ENDPOINT or
            route['sampling'] != {'max_output_tokens': 1024,
                                  'temperature': 0, 'top_p': 1} or
            route['seed'] != 20260923 or
            route['reasoning'] != {'effort': 'low'} or
            route['context_window_tokens'] != 131072 or
            route['timeout_seconds'] != 60 or
            route['automatic_retries'] != 0):
        raise ValueError('v12_route_changed')
    surrogate = dict(value, schema=teaching_v7.INPUT_SCHEMA,
                     assertion_kinds=[teaching_v7.CLAIM_KIND, 'abstention'])
    capture_v7.build_request(cf.canonical(surrogate), route)
    request = {
        'model': MODEL_ID,
        'messages': [{'role': 'system', 'content': checker.PROMPT},
                     {'role': 'user', 'content': projection.decode('utf-8')}],
        'stream': False,
        'temperature': route['sampling']['temperature'],
        'top_p': route['sampling']['top_p'],
        'max_tokens': route['sampling']['max_output_tokens'],
        'seed': route['seed'],
        'reasoning_effort': route['reasoning']['effort'],
    }
    request_raw = cf.canonical(request)
    lowered = request_raw.decode('utf-8').lower()
    # Additional known-game guard against a specific answer hidden inside an
    # otherwise permitted string. Source reprojection is the primary check.
    if any(token in lowered for token in ('rc8', 'b1=q', 'rxb1',
                                          'b2b1q', 'h8c8', '283 cp')):
        raise ValueError('v12_answer_leak_in_request')
    if capture_v7._strict_response_json(request_raw) != request:
        raise ValueError('v12_request_roundtrip_changed')
    return projection, request_raw
