# V5b: keep a malformed model response in the right bucket

The v5 Chess.com practice request was frozen but never sent. Its runner has two
response parsing defects that matter before a one-attempt call. Python's JSON
float parser turns `1e999` and `-1e999` into infinity, even though the runner
already rejects the literal tokens `Infinity`, `-Infinity`, and `NaN`. An
overflow in an extra field could therefore leave the model identity looking
valid and let `_model_content` accept an otherwise valid answer. A deeply
nested extra field raises `RecursionError`; the old capture path records that
as `transport_failure` after retaining the HTTP bytes, and its readback can
raise again. Neither outcome should be presented as a transport observation.

I copied the runner to `scripts/chess_no_forward_teaching_capture_v5b.py` and
gave the manifest, result, and evaluation separate v5b schemas. The v5 source,
tests, and original frozen request remain byte-identical. The v5b parser now
checks every JSON floating-point token for finiteness, including tokens in
nested or otherwise unused fields. It converts parser recursion exhaustion
to a bounded invalid-envelope error. This leaves the raw response intact and
marks its model identity `unverified`; it cannot enter offline evaluation.
The no-forward generator projection is still the same nine pre-move fields,
and the v5 checker is unchanged.

The new regression tests first ran against the copied parser and failed in
three specific cases: both exponent overflows were accepted as content, and
the deep response was mislabeled `transport_failure` (9 passed, 3 failed).
After the parser change, the focused v5b and original v5 capture suites passed
**21 tests**. The fake transport cases check raw-byte retention, stable
`identity_unverified` status, rejection from evaluation, and readback. These
are synthetic software tests. The separate [repair evidence](../artifacts/chess-no-forward-teaching-capture-v5b/repair-evidence-20261006.json)
reproduces the old parser defects without calling a model and verifies both
frozen folders. Its SHA-256 is
`e12e51697958d1998781b2bf2c801a6eb9c27ea22eaf96229266e6e37ae438b6`.

## Frozen request and exact identities

| Item | SHA-256 |
| --- | --- |
| Original v5 runner | `d3159affb753f33e19db4ee2d34ad3fd67a0bea0c574630717ff52484c4d14c4` |
| Original v5 tests | `beaf8d4b0b0194d9ae68119e21c9fb718c803ae024277e6453f753789db2b881` |
| Original v5 manifest | `327577e8ebe0d057f49577c689f2d531a9304da37e9150cf96c586ee41db3842` |
| V5b runner | `c65635dd88ba8d2aa98aa5562940323f5044b8278670cbc569cb2ee849bd97cf` |
| V5b tests | `127242ec4ffe1a855e4146742e6dbece60833bf8a567816ba30533945f84c30c` |
| V5b manifest | `05d8caa2dbdfe7d61bce72ea55df0faafbf9b981db67ad7c890ef0721522a946` |
| Shared nine-field projection | `b028d0c93b7362a1d5002c9d5f5a3dbfe629f0ceafa5d8daac15e2ed7e53068c` |
| Shared local request | `c30ac434904d72149bcd091e24e7dd777eba7e82bea0c76cb78e4aa8834f4c8d` |

The new create-only folder is
`artifacts/chess-no-forward-teaching-capture-v5b/chesscom-184866057876/played-frozen-20261006`.
Freeze/readback verified its source game, packet, route attestation,
implementation hashes, nine-field projection and request. Both original v5
and new v5b folders report `status=frozen`, `attempts_consumed=0`, and
`model_calls=0`. There is no `request.json`, `result.json`, or raw response in
either folder. This keeps the actual model denominator at **0/0**, with no
chess explanation quality result.

Before spending the v5b one-call attempt, use the project-native finite
source-review route to inspect the exact new runner, meaningful tests, and
retained test result. Require a concrete function-level verdict and read the
bound receipt. A passing transport or valid JSON still does not establish
why Stockfish preferred a move, teaching usefulness, Chess.com parity, or
the broader no-forward commentary gate. If the call fails, retain its single
attempt and exact raw bytes; do not retry the same frozen folder.
