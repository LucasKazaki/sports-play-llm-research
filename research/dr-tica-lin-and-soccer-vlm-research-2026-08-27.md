# Dr. Tica Lin and the research neighborhood for PlayGround

**Prepared:** 27 August 2026  
**Audience:** Archit / technical research discussion  
**Evidence rule:** claims below are paraphrased from official project pages, publisher records, accepted-paper pages, or author-hosted preprints. Performance reported by other authors has not been reproduced in this repository.

## The precise connection

Tica Lin is a Senior Research Scientist at Dolby Laboratories, a consultant to the Taiwan Institute of Sports Science, and a Harvard computer-science PhD whose research combines human–AI interaction, visualization, and sports analytics. Her sports systems mostly **assume or derive structured evidence before a language model explains it**. PlayGround tests the missing upstream capability on genuine SoccerNet footage: can a VLM recover a defensible soccer-play label directly from silent broadcast pixels?

This is complementary, not duplicative:

1. **Perception:** PlayGround currently asks a frozen VLM to infer a closed-set play label from ordered visual frames.
2. **Evidence-grounded explanation:** Lin's Sportify and VIRD show how detected actions, tactics, poses, trajectories, and source video can support explanations and drill-down.
3. **Inspectable interaction:** *Who's That Player?* shows why the system's interpretation must be visible and why a low-cost correction path is separate from transparency.

## Claim-level evidence from Dr. Lin's work

| Work | What the primary source supports | What PlayGround should adopt | What it does **not** establish |
|---|---|---|---|
| [Sportify](https://arxiv.org/abs/2408.05123), IEEE TVCG / VIS 2024 | A basketball QA system combines action/tactic pipelines, structured game context, a text-only LLM using retrieval/reasoning prompts, narratives, and embedded Pass/Cut/Screen visualizations. Its official project page explicitly says multimodal LLMs underperform and are costly for the domain-specific perception tasks it needs. | Keep perception, explanation, and presentation as separately testable layers. A fluent narrative should consume structured, inspectable evidence rather than serve as evidence itself. | It is not an end-to-end raw-video VLM, a soccer benchmark, or a comparable accuracy baseline for this six-window run. |
| [VIRD](https://arxiv.org/abs/2307.12539), IEEE TVCG / VIS 2023 | The system converts badminton match video into CV-derived player poses, shot trajectories, synchronized video, and reconstructed 3D views; its top-down workflow moves from match summary to individual rallies and shots and was evaluated with high-performance coaches and a player on real matches. | Let an analyst move from aggregate behavior to a specific answer, cue interval, region, and source frame. Evaluate whether the representation supports verification, not only whether it looks compelling. | It is a badminton CV/VR application, not an LLM play classifier. “End-to-end” describes the application workflow rather than one learned model. |
| [SportsBuddy](https://arxiv.org/abs/2502.08621), PacificVis 2025 | Player tracking, in-video highlights, timeline tracks, captions, and sharing support context-linked sports storytelling; the paper reports more than 150 users at submission and real-world case studies. | If the perception layer becomes reliable, expose editable video-linked evidence and narratives on a timeline rather than returning only prose. | Deployment and usability evidence do not validate automated play labels or grounding. |
| [The Ball is in Our Court](https://arxiv.org/abs/2211.07832), IEEE CG&A 2023 | Sports evidence is spatial, highly temporal, and user-specific. The paper emphasizes domain-expert collaboration, explicit stakeholder differences, access constraints, component isolation, and evaluation in the intended workflow. | Select one user role, co-design the evidence contract with soccer experts, preserve private-data constraints, and evaluate component effects before a long-term field study. | It is a design-methodology article, not model-performance evidence. Simulated or Wizard-of-Oz components isolate interface questions and must not be presented as perception results. |
| [Who's That Player?](https://vcg.seas.harvard.edu/publications/who-s-that-player), IEEE TVCG / VIS 2026 | In an XR soccer system, spoken queries exhibit referential, spatial, temporal, and metric ambiguity. A within-subject study (`N=16`) associated externalized interpretations with higher inspectability on most measured dimensions, but repair occurred in only 38% of deliberately misaligned externalization trials. | Show the interpreted task, selected time window, evidence, and uncertainty. Add direct correction controls; visibility alone does not ensure that a user catches or repairs a wrong interpretation. | This is an HCI/XR interaction result, not evidence that VLM perception is correct. The voice-only baseline also leaves a visual-richness confound, which the authors acknowledge. |
| [PanoCoach](https://arxiv.org/abs/2409.13859), VIS 2024 workshop | A preliminary mixed-reality soccer prototype explores how coaches communicate spatial tactics across a 2D tablet and an immersive player view. | Long-term coach-facing work should preserve spatial relations and viewpoint changes. | It does not recognize plays. The paper says its conceptual illustrations were DALL-E-generated, so none are used in this no-AI-imagery presentation. |

## Adjacent technical work and the remaining gap

| Research line | Primary-source result | Constraint on this project |
|---|---|---|
| [SoccerNet-v2](https://openaccess.thecvf.com/content/CVPR2021W/CVSports/html/Deliege_SoccerNet-v2_A_Dataset_and_Benchmarks_for_Holistic_Understanding_of_Broadcast_CVPRW_2021_paper.html) and the [official spotting task](https://www.soccer-net.org/tasks/action-spotting) | SoccerNet-v2 releases roughly 300k annotations over 500 untrimmed matches and distinguishes action spotting, camera segmentation, and replay grounding. | Event-conditioned ten-second classification is not full-match spotting; accuracy cannot be compared with spotting mAP. |
| [Domain Adaptation of VLM for Soccer Video Understanding](https://openaccess.thecvf.com/content/CVPR2025W/CVSPORTS/html/Jiang_Domain_Adaptation_of_VLM_for_Soccer_Video_Understanding_CVPRW_2025_paper.html), CVPRW 2025 | The authors train a LLaVA-NeXT-Video derivative in stages on a curated 20k-clip mixture and report gains on soccer VQA and action classification. | It motivates a later supervised baseline, but is not comparable to a frozen-prompt, six-window feasibility run. Do not fine-tune before the task, annotations, and untouched split are stable. |
| [SoccerLens](https://arxiv.org/abs/2605.09598), 2026 preprint | The authors separately evaluate soccer event labels and structured temporal/spatial cues and report grounding below 50% for the models they test, even under the loosest cue definition. | A correct class does not establish that the model used the right moment or region. Human cue annotations and joint answer/evidence scoring are required. |
| [NExT-GQA](https://openaccess.thecvf.com/content/CVPR2024/html/Xiao_Can_I_Trust_Your_Answer_Visually_Grounded_Video_Question_Answering_CVPR_2024_paper.html), CVPR 2024 | Adds manually checked temporal grounding to video QA and evaluates answer correctness together with supporting moments. | PlayGround's emitted interval should be externally scored, not merely schema-validated. This is general video QA, not soccer. |
| [SoccerAgent / SoccerBench](https://arxiv.org/abs/2505.03735), ACM MM 2025 | SoccerBench contains around 10k multimodal multiple-choice QA pairs across 13 soccer tasks; SoccerAgent decomposes questions and invokes a distributed soccer toolbox and knowledge base. | Broad soccer QA and tool routing are prior work. The clean experiment here is direct VLM versus incrementally added soccer-state tools under the same clips and answer/evidence contract. |
| [SoccerNet game-state reconstruction](https://openaccess.thecvf.com/content/CVPR2024W/CVsports/html/Somers_SoccerNet_Game_State_Reconstruction_End-to-End_Athlete_Tracking_and_Identification_on_CVPRW_2024_paper.html), CVPRW 2024 | Provides an end-to-end tracking/identification task and pitch-relative game-state annotations for broadcast soccer. | Game-state reconstruction can become an explicit auxiliary evidence layer. It must not silently replace the VLM as the semantic labeler. |
| [Do We Need Large VLMs for Spotting Soccer Actions?](https://aclanthology.org/2025.ijcnlp-srw.6/), IJCNLP-AACL workshop 2025 | The authors spot actions from commentary windows using prompted text LLM judges without processing video frames. | Commentary is a potentially predictive modality and therefore a leakage risk, not independent visual ground truth. Score visual-only, commentary-only, and fusion branches separately. |

The defensible candidate contribution is therefore not “soccer VideoQA is new.” It is:

> A controlled study of what a VLM alone extracts from real broadcast footage, what explicit soccer-state tools add, whether the answer is supported by question-specific temporal and spatial evidence, and when the system should abstain.

## School-year research program

### Fall 2026 — establish task validity

- Build a 50-clip feasibility set from at least ten match groups, with no more than five clips per match.
- Include at least 20% background, unanswerable, or semantically close hard-negative controls.
- Double-annotate the intended answer, every visible event, answerability, replay/live status, cue interval, and cue region; adjudicate disagreements.
- Freeze an untouched match-grouped test before another model, prompt, threshold, or adaptation choice.

**Gate:** acceptable answerability and evidence agreement, a stable taxonomy, and a sealed test manifest.

### Winter 2027 — run the controlled VLM study

- Cross model × image packaging × sampling density instead of changing them together.
- Add scoreboard masking, replay-logo perturbations, and semantically matched controls to measure broadcast shortcuts.
- Compare visual-only, commentary-only, and late fusion; seal each upstream branch before comparison.
- Report requested-set reliability, strict answer correctness, joint answer/evidence correctness, match-grouped uncertainty, and selective coverage–risk.

**Gate:** reproducible estimates whose denominators, confounds, and failure modes are explicit.

### Spring 2027 — add tools and test expert verification

- Compare the direct VLM with declared game-state/trajectory/tool augmentations inspired by SoccerNet-GSR and SoccerAgent.
- Choose one user role—coach or analyst—and co-design the evidence display and correction controls.
- Measure verification time, correction rate, missed-error rate, and final decision correctness; do not rely on satisfaction alone.
- Consider LoRA/domain adaptation only after the frozen evaluation protocol is stable.

**Gate:** experts verify or correct outputs faster without reducing correctness, and each gain can be assigned to a declared component.

## Questions to resolve with Archit

1. Freeze event-window classification/QA first, or pivot immediately to full-match spotting?
2. Is the first intended user a coach, analyst, referee, or fan?
3. Which evidence is mandatory: cue timestamps, broadcast-image regions, calibrated pitch coordinates, player relations, or trajectories?
4. What agreement threshold is sufficient to freeze the first annotation protocol?
5. Should the first tool ablation use game-state reconstruction, trajectory evidence, retrieval, or a combination?

