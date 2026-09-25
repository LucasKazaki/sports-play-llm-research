# Primary-source decisions for typed chess evidence

Checked 2026-09-22 UTC. This note informs an implementation; it is not an experiment result.

- [python-chess engine documentation](https://python-chess.readthedocs.io/en/latest/engine.html#chess.engine.Score) distinguishes centipawn and mate score objects, attaches a viewpoint and warns that reducing both zero-mate cases to the numeric zero loses the win/loss distinction. The adapter therefore preserves the retained type, viewpoint and explicit zero-mate direction. Tests exercise both directions using labelled synthetic software probes. No conversion to a scalar score_cp is performed.
- [Original UCI protocol, info](https://backscattering.de/chess/uci/#info) distinguishes centipawn and mate observations and lower/upper qualifications. The adapter retains those qualifications and the original score-event/PV accounting rather than interpreting a bound as an exact result. It declines all comparative-superiority claims in this first version because this change does not implement a validated interval comparison.

The existing installed library and frozen collector remain the executable version authority; current documentation was used to check semantics, not to justify a dependency upgrade. Exact receipt bytes, legal replay and source hashes bind the new packet to the earlier real development observation. Successful checks establish software integrity and preservation, not independently reproduced scores, human explanations, teaching value, representative chess competence or sports transfer.

