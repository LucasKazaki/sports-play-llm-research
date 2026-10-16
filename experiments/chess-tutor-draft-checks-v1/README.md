# Limited post-generation draft checks

The tutor now retains separate rule-check evidence after an original manual
Queen worker closes. Raw response bytes, decoded text, parsed moves and generator
inputs remain unchanged. A missing binding or retention failure leaves the draft
available and its checks unavailable.

There are three distinct results: immediate legal replay of structured BEST_MOVE,
whether BEST_MOVE matches a supplied move, and at most two explicit canonical
ANALYSIS statements about check/mate and capture. Each statement uses its own
named legal root move. Ordinary prose, strategic reasoning and later variations
are unassessed. There is no whole-explanation badge, repair, engine call or model
retry. The optional trained tutor profile remains disabled.

Both implementation and independent review passed 100 relevant CPU/UI checks;
the existing real-engine test was intentionally deselected. The four complete
finite source bundles, exact seven-path source manifest, unchanged boundary pins,
test output and independent source verdict are retained here. This is a software
review, not human semantic validation or a model-quality result.

Root inspected all five states in an explicitly fictional rendering fixture,
including different ANALYSIS/BEST/supplied moves, exact-span disclosure and stale
export exclusion followed by return. Desktop and 390-pixel narrow views were
checked in dark/light appearance and 200% text sizing. That sizing is not a
browser-zoom test. Its sticky banner appears at the current scroll position in
the full-page image; the fixture remains visibly labeled and scrollable. A body
keyboard-scroll attempt failed and no production source was changed for it.
The production module's disclosure-state cache is covered by the actual Node
module test; the standalone fixture does not substitute for production API QA.

The reviewed code is loaded in the live tutor. Actual Stockfish 19 and restored
CPU forecasting completed on the illustrative opening: c3, Bb6, d4 were legal;
the first half-move agreed with this engine search. The current evidence export
and desktop/mobile screenshots are retained. This single exploration is not a
new benchmark. No Queen request ran in that live check.

Two limitations remain explicit. The strict saved-response compatibility attempt
failed before its checker call because an old response's input hash did not equal
the original pretty input-file byte hash. No expected hash was reconstructed.
A proposed one-request authored Queen integration smoke was then not admitted
because Windows commit headroom was below the unchanged 10 GiB startup reserve.
It created no worker, request, response or model call. Its first failing sample
was not retained; the separately timestamped follow-up sample is context only.
The new post-generation controller therefore has no actual model completion
in this cycle. Earlier real Queen UI completions remain separate evidence.

`copy-manifest.json` binds 40 exact copies. Authored fixture records and screenshots
are interface evidence; they are never model output or quality labels. The
reproduction snapshots retain original local paths and need that environment.
Weights, training corpus, creator media and recovered conversations are absent.
