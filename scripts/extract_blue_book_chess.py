"""Extract real annotated PGNs from Project Gutenberg Blue Book EPUB."""
import argparse, hashlib, html, io, json, re, zipfile
from html.parser import HTMLParser
from pathlib import Path
import chess.pgn

class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts = []
    def handle_data(self, data): self.parts.append(data)

def plain(data):
    body = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", "", data)
    return html.unescape(re.sub(r"(?s)<[^>]+>", "", body)).replace("\r", "")

def comments(game):
    return sum(1 for node in game.mainline() if node.comment)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epub", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    epub, out = Path(args.epub), Path(args.out_dir)
    digest = hashlib.sha256(epub.read_bytes()).hexdigest()
    with zipfile.ZipFile(epub) as archive:
        pages = [name for name in archive.namelist() if name.lower().endswith((".html", ".xhtml", ".htm"))]
        text = "\n".join(plain(archive.read(name).decode("utf-8", "replace")) for name in pages)
    chunks = re.split(r"(?m)(?=^\s*\[Event\s+\")", text)
    games, comment_count = [], 0
    for chunk in chunks:
        if not re.match(r"^\s*\[Event\s+\"", chunk): continue
        game = chess.pgn.read_game(io.StringIO(chunk))
        if game is None or game.end().board().ply() == 0: continue
        comment_count += comments(game)
        games.append(game.accept(chess.pgn.StringExporter(headers=True, variations=True, comments=True)))
    if len(games) < 80 or comment_count == 0: raise SystemExit("annotated_pgn_extraction_failed")
    out.mkdir(parents=True, exist_ok=False)
    (out / "annotated-games.pgn").write_text("\n\n".join(games)+"\n", encoding="utf-8")
    manifest = {"schema_version":"real-chess-source-manifest/v1", "source":{"title":"The Blue Book of Chess","ebook_id":16377,"origin":"https://www.gutenberg.org/ebooks/16377","download":"https://www.gutenberg.org/ebooks/16377.epub3.images","rights":"public_domain_in_USA","scope":"real historically played illustrative games with embedded book commentary"}, "archive":{"path":"pg16377-images-3.epub","sha256":digest}, "extraction":{"games":len(games),"comment_nodes":comment_count,"pgn":"annotated-games.pgn","synthetic":False}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"blue_book_real_corpus_ok":True,"games":len(games),"comment_nodes":comment_count,"out":str(out)}, sort_keys=True))

if __name__ == "__main__": main()
