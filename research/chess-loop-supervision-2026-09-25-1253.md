# Chess loop supervision — 2026-09-25 12:53Z

## Repeated generic refresh: no executor handoff or chess credit

Slot 33 director event `c269c847-7b57-49b2-b2fb-d060c85f7b60` dispatched
task `research-refresh-8fabe8274b13e763dd71277c7b44e5eb6f95e4307d83210b`
and local run `73037e96-4852-4124-8601-65d370a8bbb0`. The LM Studio
`loops-cpu-gpt-oss-20b` run settled unverified from 11:37:05Z to 11:38:08Z
after 63,177 ms, consuming 112,792 input, 888 output, and 489 reasoning
tokens (nine tool calls; no native job). Its raw output SHA-256 is
`209870ca3e12c91690144ce61acb4e71e4413c6da4c12323f92c3360641d039c`.

This was the exact known failed generic packet (instruction SHA-256
`b22968842311219b1a63532ceb1ec145fdd0a9118f39a6d23609db42bba0a0bd`) and
returned `needs_review` / `verification_status: rejected`, with the established
fingerprint `4f98ae9d998182e974a34bf1f6dce1b2ba51bf859a07cc6d58a23a1c776c7ba5`.
It listed files, encountered an `EISDIR` read, and reread the gate four times;
it retained no evidence, actions, files, commands, tests, browser requests,
follow-ups, source proposal, executor request, writer handoff, or callback.
This is a reproducible forbidden repeat, not measurable progress. Do not replay
the packet.

At 11:59Z, separate source revalidation task `12eac902-b0ee-4192-a524-2c5889165279`
/ run `5b87f360-3082-4c3c-988d-42fa7d5c800f` retained browser receipt
`c8260d293794454a4b56cbf3f57f3eca1598d973671047e66d957aac044788ad` and
independent receipt `6486a197883d018d00d0bbc98bba2a8fc8dd9beddc9002a957aba0907f38a334`
for changed python-chess engine documentation. The runtime explicitly records
no source-specific material-change policy or implementation/evaluation decision;
therefore this observation receives no chess-progress credit. No project source,
test, artifact, data, state file, commit, native job, or test receipt changed
after the prior check-in. The no-forward gate remains planned and unachieved.

The smallest cause remains Studio-owned generic-packet settlement without a
required bounded executor/writer/callback handoff. Project-local authority does
not permit editing that runtime route, replaying retained work, or inventing a
duplicate task; preserve the evidence and require the owning Studio workflow to
enforce a complete handoff before another local budget is consumed.
