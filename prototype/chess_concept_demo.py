"""Evidence-only local preview for the Chess Concept Model feasibility packet.
It never turns engine candidates or fixture data into a human explanation.
"""
import argparse
import json
import threading
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from chess_concept_schema_validator import validate_position

LOOPBACK_HOST = "127.0.0.1"

PREVIEW_HTML = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Chess Concept Model — local preview</title><style>body{font-family:system-ui,sans-serif;max-width:56rem;margin:2rem auto;padding:0 1rem;color:#16202a;background:#f7fafc}h1{margin-bottom:.25rem}.notice{padding:1rem;border-left:5px solid #9a3412;background:#fff7ed}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0f172a;color:#e2e8f0;padding:1rem;border-radius:.4rem}</style><body><h1>Chess Concept Model</h1><p>Evidence-only local preview. This screen does not run a chess engine or a language model.</p><div id="status" class="notice">Loading the local, fixed packet…</div><pre id="payload" aria-label="Review payload"></pre><script>const status=document.getElementById('status'),payload=document.getElementById('payload');fetch('/api/review',{cache:'no-store'}).then(r=>r.json()).then(data=>{status.textContent=data.reason==='local_generator_not_configured'?'Validated packet; the configured result is an intentional abstention.':'Preview blocked safely: '+data.reason;payload.textContent=JSON.stringify(data,null,2);}).catch(error=>{status.textContent='Preview request failed safely.';payload.textContent=String(error);});</script></body></html>"""

def board_rows(fen):
    rows = []
    for rank in fen.split()[0].split("/"):
        row = []
        for cell in rank:
            row.extend(["."] * int(cell) if cell.isdigit() else [cell])
        rows.append(" ".join(row))
    return rows

def review(packet):
    gate = validate_position(packet)
    if not gate["valid"]:
        return {
            "schema_version":"chess-concept-demo/v1", "abstain":True,
            "verdict":"abstain", "confidence":0.0, "concepts":[],
            "engine_evidence_refs":[], "commentary_evidence_refs":[],
            "reason":"invalid_position_evidence", "validation_errors":gate["errors"],
            "limitations":["The local packet did not meet the evidence gate.", "No chess explanation was generated."]
        }
    return {
        "schema_version":"chess-concept-demo/v1", "abstain":True,
        "verdict":"abstain", "confidence":0.0, "concepts":[],
        "engine_evidence_refs":[], "commentary_evidence_refs":[],
        "reason":"local_generator_not_configured", "board_before":board_rows(packet["fen"]),
        "move_uci":packet["move_uci"], "legal_replay_hash":packet["legal_replay_hash"],
        "recorded_legal_board_verified":packet["legal_board_verified"],
        "source":{"source_id":packet["source"]["source_id"],"license":packet["source"]["license"],"rights_status":packet["source"]["rights_status"]},
        "engine_candidates":[{"id":v["id"],"move_uci":v["move_uci"],"score_cp":v["score_cp"]} for v in packet["engine_evidence"]],
        "commentary_sources":[v["source_ref"] for v in packet["commentary_evidence"]],
        "limitations":["No local generator is configured.","Engine candidates are evidence, not a human explanation.","No FIDE-level claim is supported."]
    }

def make_preview_server(packet, host=LOOPBACK_HOST, port=8782):
    if host != LOOPBACK_HOST:
        raise ValueError("preview host must be 127.0.0.1")
    payload = json.dumps(review(packet), sort_keys=True).encode("utf-8")
    class PreviewHandler(BaseHTTPRequestHandler):
        def _send(self, status, content_type, body):
            self.send_response(status); self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/": self._send(200, "text/html; charset=utf-8", PREVIEW_HTML.encode("utf-8"))
            elif path == "/api/review": self._send(200, "application/json; charset=utf-8", payload)
            elif path == "/health": self._send(200, "application/json; charset=utf-8", b'{"status":"ok","scope":"loopback-only"}')
            else: self._send(404, "application/json; charset=utf-8", b'{"error":"not_found"}')
        def log_message(self, format, *args):
            return
    return ThreadingHTTPServer((host, port), PreviewHandler)

def preview_readiness(packet):
    server = make_preview_server(packet, LOOPBACK_HOST, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = "http://%s:%d" % (LOOPBACK_HOST, server.server_port)
        health = json.loads(urlopen(base + "/health", timeout=3).read())
        payload = json.loads(urlopen(base + "/api/review", timeout=3).read())
        safe_abstention = payload.get("verdict") == "abstain"
        return {
            "schema_version": "chess-concept-preview-readiness/v1",
            "ready": health == {"status": "ok", "scope": "loopback-only"} and safe_abstention,
            "url": base + "/", "scope": "loopback-only",
            "review_reason": payload.get("reason"), "safe_abstention": safe_abstention,
        }
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()

def load_packet(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as error:
        return None, str(error)

def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a local, evidence-only Chess Concept packet.")
    parser.add_argument("--packet", required=True, help="PositionEvidenceV1 JSON file")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--model", action="store_true", help="Run the guarded local LM Studio model once")
    parser.add_argument("--serve", action="store_true", help="Serve the fixed packet on loopback only")
    parser.add_argument("--readiness", action="store_true", help="Run a finite loopback-only preview readiness check")
    parser.add_argument("--host", default=LOOPBACK_HOST)
    parser.add_argument("--port", type=int, default=8782)
    args = parser.parse_args(argv)
    packet, error = load_packet(args.packet)
    if error:
        print(json.dumps({"schema_version":"chess-concept-demo/v1","verdict":"abstain","reason":"packet_read_error","detail":error}))
        return 2
    if args.readiness:
        status = preview_readiness(packet)
        print(json.dumps(status, sort_keys=True))
        return 0 if status["ready"] else 2
    if args.model:
        from chess_concept_model import generate
        result = generate(packet)
        print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
        return 0 if not result["abstain"] else 2
    if args.serve:
        try:
            server = make_preview_server(packet, args.host, args.port)
        except (OSError, ValueError) as error:
            print(json.dumps({"schema_version":"chess-concept-demo/v1","verdict":"abstain","reason":"preview_start_error","detail":str(error)}))
            return 2
        print(json.dumps({"schema_version":"chess-concept-preview/v1","url":"http://%s:%d/" % (args.host, server.server_port),"scope":"loopback-only"}), flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
        return 0
    result = review(packet)
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["reason"] == "local_generator_not_configured" else 2

if __name__ == "__main__":
    raise SystemExit(main())