# Official SoccerMaster execution plan — supervisor source inspection

Internal working note, 2026-09-14 UTC. SYSTEMS GO / SEMANTIC NO-GO. This is a source-derived implementation plan, not an official model run or promoted research result.

## What the source now establishes

The public repository tree returned revision `2e5619712d93f634b841aaf37231cd9fceb6b262`. Eight files fetched by the GitHub connector are retained as inert source text in `artifacts/supervisor-20260914/official-source-audit-v1/source-records.json`. The corrected native AST audit dca5cc73-cb0e-4516-9f99-9a3688a921b2 / job2f26fa82-6490-4c23-bd65-b11ef327e250 succeeded with all eight Git blob identities matching and23orderedclasses. The initial prelaunch failure remains preserved. No official source was imported, no weights acquired and no model executed; see contract-audit.json beside the source records. A verified development-only silent10second clip is also ready (development-clip-v1/manifest.json), but official inference and scientific eligibility remain open.

- [inference_demo.py](https://github.com/haolinyang-hlyang/SoccerMaster/blob/2e5619712d93f634b841aaf37231cd9fceb6b262/codes/SoccerMaster/inference_demo.py) constructs random tensors. Its successful output would establish a setup smoke test, not soccer evidence.
- [multi_task.py, load_checkpoint](https://github.com/haolinyang-hlyang/SoccerMaster/blob/2e5619712d93f634b841aaf37231cd9fceb6b262/codes/SoccerMaster/models/multi_task.py#L213) warns and continues when backbone/head files are absent, and uses strict=False for backbone state. A project wrapper must independently require exact files/hashes and reject unexpected missing/unexpected keys. A process exit of zero cannot establish checkpoint loading.
- [caption_classification.py](https://github.com/haolinyang-hlyang/SoccerMaster/blob/2e5619712d93f634b841aaf37231cd9fceb6b262/codes/SoccerMaster/models/caption_classification.py) receives global_features and returns logits/features. Its class count derives from the ordered 23-item keywords_list in [data/video_caption.py](https://github.com/haolinyang-hlyang/SoccerMaster/blob/2e5619712d93f634b841aaf37231cd9fceb6b262/codes/SoccerMaster/data/video_caption.py). Do not silently map this to the paper's reported 24-class scope or invent a background class.
- Canonical MultiTaskingModel imports all detection/line/keypoint/caption branches at module load. CaptionClassification imports video_caption, which imports decord and data.utils. Configuration that turns off unwanted heads does not itself eliminate those imports.
- [pretrain.yaml](https://github.com/haolinyang-hlyang/SoccerMaster/blob/2e5619712d93f634b841aaf37231cd9fceb6b262/codes/SoccerMaster/configs/pretrain.yaml) specifies 30 frames, 512 resize, temporal layer16, hidden dimension1024 and SigLIP2 local paths. [default.yaml](https://github.com/haolinyang-hlyang/SoccerMaster/blob/2e5619712d93f634b841aaf37231cd9fceb6b262/codes/SoccerMaster/configs/default.yaml) supplies keep_aspect_ratio=False and mean/std=[0.5,0.5,0.5]. These are source values; actual ToTensor/resize numerical behavior and frame-sampling parity still require executable comparison.

## Concrete asset metadata

Read-only Hugging Face API observations on 2026-09-14 found model revision `0d94573662dbd678df22aa5c61ae77f474b939c9`, public and ungated, with model-card license metadata apache-2.0. No weights were downloaded and no license accepted. This observation does not resolve all code/data/use rights.

| File | Remote size | Advertised LFS SHA-256 |
| --- | ---: | --- |
| backbone.pt | 1,435,246,749 bytes | d8a8932d844cc2756277ec485e36615b1196f1ad747240edb46b77e870fd9660 |
| CaptionClassification.pt | 100,892,440 bytes | bee4abe25ae16861f757c69b643cfe859aed9ca2d45145ce12e39979d967d604 |

The advertised hash must be checked against actual bytes after any permitted acquisition. Model revision is not a file digest. The SigLIP2 repository returned revision `49488218e80259885f3be61d7a9455faf833b7a8`, public/ungated and apache-2.0 metadata. It includes model.safetensors plus vision/text/tokenizer configuration; required actual assets remain to be pinned.

Sources: [SoccerMaster metadata](https://huggingface.co/api/models/xleprime/SoccerMaster), [file metadata](https://huggingface.co/api/models/xleprime/SoccerMaster/tree/main?recursive=true), [SigLIP2 metadata](https://huggingface.co/api/models/google/siglip2-large-patch16-512).

## Smallest honest execution milestone

1. Finish the static source/blob audit and inspect the exact transitive imports for the chosen encoder/head path. Preserve any compatibility patches separately from upstream source.
2. Acquire only the permitted, digest-bound required assets through an authorized mechanism. The existing public-wheel broker has a 50MiB wheel-only limit and is not an official checkpoint downloader. Do not disguise weights as packages or bypass that broker.
3. Resolve actual project dependencies and freeze versions; do not install the entire annotation pipeline speculatively. Selected project Python currently lacks torch and transformers. Missing computation-scope paperwork is not a request to repeat the already-granted local execution permission.
4. Use the prepared fixed SoccerTrack117092 development excerpt once its source-hash/silent-decode job succeeds. Never substitute the sealed128057 test match, open BAS labels for selection, or claim the excerpt is benchmark-eligible.
5. Implement a local wrapper that requires exact checkpoint bytes, records load-key compatibility, pins eval preprocessing/sampling and label order, runs with no text/commentary/annotations, and preserves raw logits/features, finite/shape checks, source/config/input hashes, cold/warm time and actual peak memory. Fit cannot be inferred from file size.
6. Treat this as one development feasibility result. Independent annotations, calibration, match-disjoint evaluation, frozen coach relevance judgments and actual utility evidence remain separate unfinished work.

The fresh native inventory `artifacts/supervisor-20260914/official-inventory-v1.json` still has15 blockers and zero model/official/checkpoint calls. No blocker is marked closed by this note.
