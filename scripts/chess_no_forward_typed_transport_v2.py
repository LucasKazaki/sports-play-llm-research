"""Versioned typed-output transport for a single frozen chess development input.

The existing no-forward runner still owns source checks, input isolation, attempt
accounting and raw-response retention. This adapter only adds an output-format
instruction. It must be frozen before a call and never receives evaluator data.
Its result is a local development probe, not an accepted explanation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import chess_counterfactual_evidence as cf
import chess_no_forward_generation_runner as runner
import chess_no_forward_packet as no_forward


SCHEMA = 'chess-no-forward-typed-transport/v2'
PROMPT = """You are explaining one selected chess move from a pre-move position.
Return only a JSON object with exactly two keys: schema and assertions.
schema must be \"chess-no-forward-commentary-output/v1\".
assertions must contain 1 to 16 objects of these forms:
{"kind":"legal_board_fact","field":"selected_move.san","value":"COPY_EXACT_INPUT_VALUE"}
{"kind":"retained_engine_observation","score":COPY_EXACT_INPUT_SCORE_OBJECT}
{"kind":"bounded_strategic_hypothesis","concept":"ONE_INPUT_VOCABULARY_VALUE","evidence":[ONE_OR_MORE_LEGAL_BOARD_FACT_OR_ENGINE_OBSERVATION_OBJECTS],"uncertainty":"WHY_THIS_IS_ONLY_A_HYPOTHESIS"}
{"kind":"abstention","reason":"WHY_THE_EVIDENCE_IS_INSUFFICIENT"}
Use only field names and exact values present in the supplied input. A board fact
field may be side_to_move, selected_move.uci, selected_move.san, or a field in
transition. Copy the entire score object exactly if you cite the engine.
Choose a strategic concept only when the pre-move board and selected move support
it; identify uncertainty. A score is an observation, not an explanation or a
proof of best play. If you cannot support an idea, output a sole abstention.
Do not supply prose outside JSON or invent a continuation, forced result,
opponent reply, move classification, or human coaching judgment."""
PROTOCOL_FILE = 'typed-transport-protocol-v2.json'
REQUEST_FILE = 'typed-request-v2.json'


def build_request(canonical_packet: bytes, route: dict) -> bytes:
    """Construct the sole model request from an exact no-forward packet."""
    runner._validate_route(route)
    cf.require(type(canonical_packet) is bytes and
               0 < len(canonical_packet) <= runner.MAX_PACKET_BYTES,
               'invalid_typed_transport_packet_bytes')
    try:
        packet = json.loads(canonical_packet)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_typed_transport_packet_json') from error
    no_forward._shape(packet)
    cf.require(cf.canonical(packet) == canonical_packet,
               'typed_transport_packet_not_canonical')
    request = {
        'model': route['model_id'],
        'messages': [
            {'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': canonical_packet.decode('utf-8')},
        ],
        'stream': False,
        'temperature': route['sampling']['temperature'],
        'top_p': route['sampling']['top_p'],
        'max_tokens': route['sampling']['max_output_tokens'],
        'seed': route['seed'],
        'reasoning_effort': route['reasoning']['effort'],
    }
    return cf.canonical(request)


def _protocol(run_dir: Path, route: dict, packet_sha256: str) -> dict:
    return {
        'schema': SCHEMA,
        'runner_manifest_sha256': cf.file_digest(run_dir / 'manifest.json'),
        'adapter_sha256': cf.file_digest(Path(__file__)),
        'prompt_sha256': cf.digest(PROMPT.encode('utf-8')),
        'packet_sha256': packet_sha256,
        'route_sha256': cf.digest(cf.canonical(route)),
        'request_path': REQUEST_FILE,
        'model_calls_before_capture': 0,
        'commentary_capability_gate_passed': False,
    }


def freeze_protocol(run_dir: Path) -> dict:
    """Bind source, prompt and route before allowing the one model call."""
    run_dir = Path(run_dir)
    manifest = runner._load_manifest(run_dir)
    cf.require(len(manifest['requests']) == 1, 'typed_transport_requires_one_request')
    cf.require(not (run_dir / 'results.json').exists(), 'generation_run_already_started')
    request = manifest['requests'][0]
    raw = runner._read_bytes(run_dir / request['input_path'], runner.MAX_PACKET_BYTES,
                             'typed_transport_packet_too_large')
    cf.require(cf.digest(raw) == request['input_sha256'], 'typed_transport_packet_changed')
    build_request(raw, manifest['observed_route'])
    protocol = _protocol(run_dir, manifest['observed_route'], cf.digest(raw))
    runner.write_json(protocol, run_dir / PROTOCOL_FILE)
    return protocol


def build_transport(run_dir: Path, *, opener=None):
    """Write the exact request before POST; never redirect, proxy or retry."""
    run_dir = Path(run_dir)
    manifest = runner._load_manifest(run_dir)
    protocol = runner._read_json(run_dir / PROTOCOL_FILE)
    cf.require(protocol == _protocol(run_dir, manifest['observed_route'],
                                    manifest['requests'][0]['input_sha256']),
               'typed_transport_protocol_binding_changed')
    route = manifest['observed_route']
    if opener is None:
        opener = build_opener(ProxyHandler({}), runner._NoRedirect())

    def transport(canonical_packet):
        cf.require(cf.digest(canonical_packet) == protocol['packet_sha256'],
                   'typed_transport_packet_binding_changed')
        request_bytes = build_request(canonical_packet, route)
        with (run_dir / REQUEST_FILE).open('xb') as stream:
            stream.write(request_bytes)
        request = Request(route['endpoint'] + '/chat/completions', data=request_bytes,
                          headers={'Content-Type': 'application/json'}, method='POST')
        try:
            response = opener.open(request, timeout=route['timeout_seconds'])
        except HTTPError as error:
            response = error
        with response:
            body = response.read(runner.MAX_RAW_BYTES + 1)
            status = getattr(response, 'status', 200)
        cf.require(len(body) <= runner.MAX_RAW_BYTES, 'typed_transport_response_too_large')
        return {
            'raw_output': body, 'observed_route': route,
            'transport_status': 'completed' if 200 <= status < 300 else 'http_error',
        }

    return transport


def capture(data_root, source_path, source_sha256, typed_packet_path, run_dir):
    """Run one pre-frozen development probe through the existing durable runner."""
    run_dir = Path(run_dir)
    cf.require((run_dir / PROTOCOL_FILE).is_file(), 'typed_transport_protocol_missing')
    return runner.execute_frozen_run(data_root, source_path, source_sha256,
                                     typed_packet_path, run_dir, build_transport(run_dir))


def verify(data_root, source_path, source_sha256, typed_packet_path, run_dir):
    run_dir = Path(run_dir)
    integrity = runner.verify_results(data_root, source_path, source_sha256,
                                      typed_packet_path, run_dir)
    manifest = runner._load_manifest(run_dir)
    protocol = runner._read_json(run_dir / PROTOCOL_FILE)
    cf.require(protocol == _protocol(run_dir, manifest['observed_route'],
                                    manifest['requests'][0]['input_sha256']),
               'typed_transport_protocol_binding_changed')
    request_path = run_dir / REQUEST_FILE
    if request_path.exists():
        packet = (run_dir / manifest['requests'][0]['input_path']).read_bytes()
        cf.require(request_path.read_bytes() == build_request(packet, manifest['observed_route']),
                   'typed_transport_request_binding_changed')
    else:
        cf.require(integrity['model_calls'] == 0, 'typed_transport_request_missing_after_call')
    return {**integrity, 'typed_transport_verified': True,
            'request_sha256': cf.file_digest(request_path) if request_path.exists() else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze-protocol', 'capture', 'verify'))
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--source-sha256')
    parser.add_argument('--typed-packet', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'freeze-protocol':
        result = freeze_protocol(args.run_dir)
    else:
        if not all((args.data, args.source, args.source_sha256, args.typed_packet)):
            parser.error('capture and verify require --data, --source, --source-sha256 and --typed-packet')
        call_args = (args.data, args.source, args.source_sha256, args.typed_packet, args.run_dir)
        result = capture(*call_args) if args.command == 'capture' else verify(*call_args)
    print(cf.canonical(result).decode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
