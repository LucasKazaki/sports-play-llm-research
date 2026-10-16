"""Root-launched, localhost-only authored rendering fixture. No model imports."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8794);args=parser.parse_args()
    if not 1024<=args.port<=65535:raise ValueError('Choose an unprivileged local port.')
    manifest=json.loads((FOLDER/'manifest.json').read_bytes())
    for row in manifest['source_bindings']:
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('A reviewed production renderer source changed.')
    for row in manifest['files']:
        if hashlib.sha256((FOLDER/row['file']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('An authored fixture file changed.')
    routes={'/':('index.html','text/html'),'/fixture.js':('fixture.js','text/javascript'),'/renderer.js':('renderer.js','text/javascript'),'/fixtures.json':('fixtures.json','application/json'),'/style.css':('style.css','text/css'),'/coaching.css':('coaching.css','text/css'),'/fixture.css':('fixture.css','text/css')}
    pages={url:((FOLDER/name).read_bytes(),mime)for url,(name,mime)in routes.items()}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Host')not in {f'localhost:{args.port}',f'127.0.0.1:{args.port}'}:self.send_error(403);return
            page=pages.get(self.path.split('?',1)[0])
            if page is None:self.send_error(404);return
            body,mime=page;self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'");self.end_headers();self.wfile.write(body)
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    try:server.serve_forever()
    finally:server.server_close()

if __name__=='__main__':main()
