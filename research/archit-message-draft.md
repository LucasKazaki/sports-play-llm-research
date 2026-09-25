# Draft message to Archit

**Subject:** Concrete 2-week pilot plan for the soccer VLM project

Hi Archit,

I reviewed the meeting notes, the SoccerNet tooling, and recent sports-video/VLM work. I think we should start with a focused pilot instead of committing immediately to model fine-tuning.

**Proposed question:** can a VLM answer questions about 5–10 second soccer plays while grounding each answer in the correct timestamps, pitch region, and player/ball trajectory—and abstaining when the clip does not support the answer?

For the first two weeks, I propose that we:
1. confirm the lab-approved video source and data/license rules;
2. select 50 short clips and define a small question taxonomy;
3. annotate answers plus decisive frames/regions/trajectories, including unanswerable questions;
4. benchmark a direct VLM, retrieval-augmented VLM, and tracking/homography-assisted VLM;
5. evaluate answer accuracy separately from evidence correctness, calibration, latency, and compute.

I can own the reproducible evaluation harness, model/tool adapters, experiment tracking, and baseline runs. Could you own or co-own the coach-facing question taxonomy, annotation guide, dataset/lab access, and review of the sport semantics? We should cross-review at least 10–20% of the annotations.

Could you also send me:
- the current Dr. Lin/lab page (the `tjcalin.com` link did not resolve for me);
- the exact authorized dataset/video source and whether derived clips/annotations can be shared;
- the models and compute available in the lab;
- the expected summer deliverable/deadline;
- whether the primary target is clip QA/retrieval, document QA, or both?

I already have a synthetic end-to-end harness running locally (Python/FFmpeg/OpenCV) with explicit answer, temporal-evidence, spatial-evidence, calibration, and abstention fields. The synthetic metrics only validate plumbing; we will not present them as soccer-model results.

If this direction sounds right, I can send a one-page protocol and a proposed annotation template before our next meeting.

Best,
Lucas
