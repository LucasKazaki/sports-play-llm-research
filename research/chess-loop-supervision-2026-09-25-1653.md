# Chess loop supervision — 2026-09-25 16:53Z

## Repeated generic refresh consumed local budget without a usable handoff

Director slot 34 event `0b1f5722-7f37-45a8-b687-450c5696ca1f` produced
task-ready event `4c74daa8-a824-4b7a-a5a8-c49ade8b39bb` (sequence 48452),
ephemeral task `research-refresh-24fd218d8763add7a17b74719721af5db08c3c5673af266d`,
and local goal-worker run `837424f4-dbb2-4f58-807a-328cc1e5d2c1`. The
LM Studio `loops-cpu-gpt-oss-20b` run settled `unverified` from 15:38:15Z to
15:39:17Z after 61,521 ms, consuming 116,935 input, 769 output, and 417
reasoning tokens (ten requests and nine tool calls). Its raw output SHA-256 is
`52386621ea90eec3b009910b5744f0acb9a0e67b814c71a7c3cee506d5d784d8`.

It returned `needs_review` with the prior rejected-worker fingerprint
`4f98ae9d998182e974a34bf1f6dce1b2ba51bf859a07cc6d58a23a1c776c7ba5`, and
empty actions, evidence, file changes, commands, tests, browser requests, and
follow-ups. The trace listed the workspace, read only the capability gate, hit
three `EISDIR` directory-read errors, and spent its last optional read budget
without a source selection, executor request, workspace-writer handoff, or
callback. No native job ran. This is the same reproducible generic
packet/tool-selection failure recorded at 12:53Z, not measurable chess work;
do not replay it or create a duplicate project task.

Separate source-revalidation task `ec03f77e-7de3-41b9-b3b2-b58d58675829` /
run `02e76dd2-dc37-45b8-9725-7326056d64f0` settled at 16:00Z with browser
receipt `a1c95d9e8cca59d464bf76b55eb92e758d5ca780aac49a435fe878c87ff2e4d6`
and independent receipt
`2e0ae03f24cf03009cfe857b952ca9572d3be480d20c5e2c763847b73df88bae`.
It explicitly found `https://database.lichess.org/` unchanged and awarded no
progress credit. There is no owned source/test/artifact/data/state change,
focused test receipt, real-chess experiment, or independent acceptance since
the prior check-in. The gate remains planned and unachieved.

The smallest reproducible cause is still Studio-owned settlement of an
unconstrained generic refresh without an enforced bounded source/executor/writer
handoff. Project-local authority cannot modify that routing, replay retained
work, or invent a replacement task. Preserve the exact evidence and require the
owning Studio workflow to validate a complete handoff before another local
budget is consumed.
