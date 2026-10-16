# Chess research: AI assistance and data stewardship

Working record, October 16, 2026. Prepared with Codex assistance for research
review. This record is not an institutional approval, publication submission or
expert assessment of the chess tutor.

1. **Purpose and responsibility.** The current work studies whether a local
   chess-language model can choose legal moves, forecast short continuations and
   produce accurate, useful explanations. A named human research owner, UMD
   auspices, contributor credit and any sponsor or venue requirements remain to
   be established by the actual collaborators. Neither Archit nor a tutor has
   been contacted by this work.

2. **AI and engine roles.** Codex assists project-history retrieval, literature
   review, software, protocols, debugging, experiment operation and these notes.
   Separate local agents inspect source and closed evidence; they are AI
   reviewers, not human chess experts or independent laboratories. Local Queen
   PAWN-8 generates uncorrected chess responses and receives actual local LoRA
   gradient updates. Stockfish19 supplies bounded search references. Rule-based
   replay supplies legal-move and narrow factual checks. An engine match,
   software test or agent consensus does not establish teaching quality.

3. **Data and permitted use.** The coaching corpus uses a retained Lichess
   CC0-1.0 puzzle shard pinned at dataset revision
   `461725966ea46898ec6481372a6326de3281bfbd`, SHA-256
   `5352e3bff4d6163851c07a0cc922b1ff72875cc6f75d994bdfc3272a37ca9e87`.
   Intake consumes the first setup move, without source solution tails or
   themes. Game-level splits, historical board exclusions and the entire
   512-game held reservoir are retained. Targets come from deterministic board
   facts and recorded Stockfish searches. Local exclusions cannot establish
   absence from a publisher's pretraining. Recovered chats and downloaded
   GothamChess media remain private and are not model-training data. Synthetic
   positions test software and are identified separately from real-source cases.

4. **Annotation and evaluation.** The offline claim-audit inventory is manually
   authored by Codex and checked by a separate agent against exact response
   text and replayed branches. It has no expert human semantic validation and
   is an engineering diagnostic, not human gold annotation. Unsupported claims
   and illegal earlier contexts remain unassessed. The current coaching pilot
   selects checkpoints using development data only. Its planned fresh matched
   panel separates free move choice from explanation of a supplied move, but
   the actual first comparison stopped before any trained-panel call. The
   separate later 96-response checkpoint comparison remained entirely unrun.
   Neither provides a matched coaching-improvement score. These panels do not
   measure student learning, chess Elo or comprehensive explanation quality.
   Keep failed, unknown and never-run outcomes in their denominators.

5. **Reproduction and preservation.** Retain pinned upstream Queen code
   `c372da22ca75e95c3c79bee8a83c220fc54d0dcb` and checkpoint
   `5027687fac08b64b2403b13aca5b198e68294fe9`, component notices, exact source
   snapshots, environment versions, seeds, frozen protocols, selection files,
   raw requests/responses, resource journals, failure receipts and hashes.
   Public repository evidence contains bounded protocols and permitted
   software/result records. Private weights, source-game records, recovered
   chats and creator media are excluded. Source-code licensing does not alone
   grant permission to redistribute every weight or component. Backups,
   access ownership, retention period and any future institutional repository
   still require an actual research-owner decision; no backup is asserted here.

6. **Human review and future use.** The local interface attributes engine,
   deterministic-rule and learned-model outputs separately. Raw model prose can
   be false and remains a draft. Tutor demonstration can expose failures for
   feedback; professional coaching and the repository's formal commentary and
   shareable-candidate gates remain unpassed. Any later systematic participant
   study needs its actual data-handling and applicable institutional
   determination. This work has collected no tutor or student study records.

The [UMD research-fit note](chess-umd-research-readiness-2026-10-16.md) records
official guidance and unresolved questions. The
[current research radar](chess-research-radar-2026-10-16.md) records the search
scope and paper versions. This working disclosure should be reconciled with
the final method and the intended venue before any submission.
