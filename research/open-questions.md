# Questions for Archit and the Lab

## Ask in the next meeting/email
1. Which exact lab and Dr. Lin page should we use? `https://tjcalin.com/` did not resolve from Lucas's machine.
2. Is the primary deliverable a SoccerNet challenge submission, a fall coach-facing system, a workshop paper, or a full conference paper? What deadline?
3. Which SoccerNet task/data is already downloaded and authorized: VQA, action spotting, captioning, tracking, calibration, game-state reconstruction, or other?
4. Does the lab/Huddle partner permit research use and publication of clips, documents, derived annotations, and screenshots? What IRB/data agreement applies?
5. What models, API credits, GPUs, storage, and prior code are available? Can Archit share the current baseline and dataset schema?
6. Who will annotate/validate tactical questions? Can coaches review a small blind evaluation set?
7. Is halftime latency a hard requirement? Target clip library size, query latency, and interface device?
8. Does “sports plays” mean soccer only for the paper, or should transfer to basketball/football be evaluated?

## Go/no-go gates
- **G1:** Data access/license confirmed.
- **G2:** 50-clip pilot and annotation rubric approved.
- **G3:** Direct VLM baselines run with failure taxonomy.
- **G4:** Proposed method beats a strong baseline on grounded metrics, not only subjective examples.
- **G5:** Expert/coach evaluation and reproducibility package feasible before submission deadline.

The exact G1 source options, rights questions, manifest fields, and approval wording are frozen in `research/rights-and-source-decision-packet.md`. Until its mandatory acquisition gate is satisfied, real-video acquisition is NO-GO.
