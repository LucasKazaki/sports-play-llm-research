# Local chess evidence inspector

This view extends the existing fixed-packet preview. It displays retained records;
it does not run a model or engine, replay legality, verify hashes, or accept a
research capability claim.

From the repository root:

```powershell
& .\.venv-soccernet\Scripts\python.exe .\prototype\chess_concept_demo.py --packet .\demo\chessconcept-evidence-only-fixture-v1.json --serve --port 8782
```

Open `http://127.0.0.1:8782/` and choose **Open development set**. The initial fixed
fixture is deliberately rejected by the existing evidence gate; the development
action opens the already-versioned eight label-free source boards. It does not
turn the fixture or the historical baseline into a new model result. Stop the
owned preview with Ctrl+C when finished.

**Open result JSON** reads a local file in the browser. File contents are not sent
to the server. Supported contracts are:

- `chess-dev-source-projection/v1`: source boards, game links and stated limits.
- `chess-typed-position-evidence/v1`: retained candidates, typed score/bound/
  perspective, board facts, and retained after-board when supplied.
- `chess.stockfish-distillation.v1` / `.v2`: baseline/trained raw output by evaluation
  split, complete reported denominators, checkpoint identity, and limitations.
- `chess-concept-demo/v1`: the existing fixed preview, including safe abstention.

Imports are labelled unverified. Legal and teacher-match flags remain
receipt-reported values. The viewer preserves missing condition records and
rejects duplicate identities within a condition. It does not compare unrelated
positions merely because their IDs match. A reported legality decline remains
visible as a regression; it cannot be replaced by a lower training-loss claim.

The board starts with White at the bottom. **Flip board** changes orientation
without changing the input position. Arrow keys, Home and End navigate the
desktop position list; compact layouts use a native selector. Before/after
controls show only retained FENs. Model outputs and source text are inserted as
text, and external game links allow HTTPS Lichess URLs only. Dark appearance,
increased contrast, reduced-motion, keyboard focus and 390 px layouts are
supported.

Verification:

```powershell
& .\.venv-soccernet\Scripts\python.exe -m pytest .\tests\test_chess_concept_demo.py -q
node --test .\tests\chess-demo-ui.test.cjs
```

Browser QA additionally covers source navigation, board orientation, a retained
after-board, a failed candidate record, inert HTML-like raw output, a real local
training receipt, and narrow-screen overflow. These are interface checks, not
scientific evaluation or shareable-candidate promotion.
