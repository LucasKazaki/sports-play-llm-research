# Chess engine provenance and search accounting — 2026-10-03

Packet: `SLM-C02-R15-ENGINE-PROVENANCE-ACCOUNTING-v1`.

Base chain head: `11626ef4e6d5993fd70f674606abe8fba6afc503`.
Current mirror production baseline: `156780d1370363ab83f64589c8bb319dde63cc9f`.
Current accepted collector blob: `7dccf3525049c60a72f0a2883709012d86d6adfb`.

Current v3 engine evidence already binds the Stockfish executable SHA-256 and requested Threads/Hash/node/MultiPV budget, and retains depth plus observed nodes. It does not retain UCI id name/author, installed python-chess version, exact active NNUE network SHA-256, seldepth, engine-reported time, or optional nps/hashfull/tbhits.

Decision: preserve historical v2/v3 bytes unchanged. Future exact C02 receipts should add one engine-run provenance envelope that binds:
- engine binary SHA-256;
- UCI id name/author;
- installed python-chess version;
- full-strength standard-chess options (Threads, Hash, MultiPV, Ponder=false, UCI_AnalyseMode=true, UCI_LimitStrength=false, Skill Level=20);
- Syzygy disabled for the first provenance schema;
- exact active NNUE SHA-256 plus reported EvalFile name and hash source;
- sanitized compiler/build fingerprint;
- requested node limit plus same-score-event depth, seldepth, nodes and time, with nps/hashfull/tbhits when present;
- R14 history SHA, observation ID and exact root move for root-restricted searches.

Stockfish's official network repository documents that the strongest net is embedded in most binaries and can be exported with `export_net`; its EvalFile name uses the first 12 hexadecimal characters of the NNUE SHA-256. Never commit exported NNUE bytes. Hash a temporary local export (or retained exact bytes) and delete/quarantine it afterward.

python-chess 1.11.2 exposes UCI engine id/options and InfoDict keys including depth, seldepth, time, nodes, nps, hashfull and tbhits. Do not backfill missing accounting from another info event.

Native fail-first: the existing v3 shape must fail the new provenance validator because UCI ID, python-chess version, active-network hash, seldepth and time are absent.

Cloud reference result: expected fail-first exit 1; 16/16 focused standard-library tests passed; py_compile passed. No Stockfish process, export_net, Company Runtime, Windows, heldout or model run was executed by the cloud pass.

Native gate remains C00 N/N+1 first. After that, integrate R15 into the single C02 collector/comparison path; do not create a second engine adapter or rewrite historical receipts.

Typed stops: `SLM-C02-R15-C00`, `-PATHS`, `-ENGINE-ID`, `-NETWORK`, `-TABLEBASE-PROVENANCE`, `-INFO-EVENT`, `-R14`.
