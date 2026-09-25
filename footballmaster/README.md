# FootballMaster standalone package

This directory is the complete American-football implementation boundary. It
owns the ontology, rights gates, feature extraction, target mapping, training,
evaluation, model package, index schema, and full-text retrieval code. It does
not import any application server or other sport package.

## Commands

Run all commands from the repository root:

```powershell
python -m footballmaster audit-data
python -m footballmaster train --out artifacts/footballmaster/run-v2
python -m footballmaster evaluate --model-dir artifacts/footballmaster/run-v2 --split test
python -m footballmaster build-index --model-dir artifacts/footballmaster/run-v2 --out artifacts/footballmaster/index-v2
python -m footballmaster search --index artifacts/footballmaster/index-v2/search-index.sqlite3 --query "touchdown pass"
python -m footballmaster verify --model-dir artifacts/footballmaster/run-v2
```

The default configuration is `resources/default-config.json`. Its ontology and
rights threshold are immutable for this model version; numeric training
settings can be changed explicitly. JSON boundary definitions live under
`schemas/`.

## Integration boundary

The package publishes hash-bound JSON, NPZ, JSONL, and SQLite artifacts. A UI
may read those artifacts through an adapter, but UI code is never imported by
this package. The model card declares `architecture_scope: football_only` so
the boundary can be checked without referencing any other research system.
