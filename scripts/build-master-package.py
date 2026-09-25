"""Assemble the internal master evidence index after successful native checks."""
import argparse, hashlib, json, re
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/master-package-20260913"
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding="utf-8-sig"))
def write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f: f.write(body)
def jsontext(value): return json.dumps(value, indent=2, sort_keys=True) + "\n"
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--verification",required=True)
    p.add_argument("--reproduction",required=True)
    p.add_argument("--jobs",nargs="+",required=True)
    args=p.parse_args()
    verify_dir=(ROOT/args.verification).resolve()
    verify_dir.relative_to(ROOT)
    verification=read(verify_dir/"verification.json")
    assert verification["passed"] is True and len(verification["stages"])==6
    assert verification["frozen_unchanged"] is True and verification["reset_applied"] is False
    log=(verify_dir/"verify.stdout.log").read_text(encoding="utf-8-sig")
    counts=re.findall(r"(\d+) passed",log)
    assert counts, "full test count not observed"
    full_count=int(counts[-1])
    reproduction=(ROOT/args.reproduction).resolve()
    reproduction.relative_to(ROOT)
    # Locate the explicit synthetic reproduction receipt by schema, without media reads.
    repro_paths=list(reproduction.glob("*.json"))
    matches=[(q,read(q)) for q in repro_paths if read(q).get("schema_version")=="playground-hosted-video-synthetic-reproduction-v1"]
    assert len(matches)==1
    repro_path,repro=matches[0]
    assert repro["synthetic"] is True and repro["real_model_calls"]==0 and repro["real_soccer_clips"]==0
    assert repro["pure_resume_preserved_seals"] is True and repro["counts"]["requested"]==6
    model=read(BASE/"model-demo-v1/summary.json")
    assert model["passed"] is True and model["checks"]==23 and model["visual_model_calls"]==0
    preflight_path=ROOT/"artifacts/soccermaster-official-preflight-20260913-v1/preflight-receipt.json"
    preflight=read(preflight_path)
    assert preflight["status"]=="BLOCKED" and preflight["model_calls"]==0
    jobs=[]
    evidence_files=[]
    for job_id in args.jobs:
        jobdir=ROOT/".agent-runtime/jobs"/job_id
        receipt_path=jobdir/"receipt.json"
        receipt=read(receipt_path)
        assert receipt["jobId"]==job_id and receipt["projectId"]=="sports-play-llm"
        commands=[]
        evidence_files.append(receipt_path)
        for i,command in enumerate(receipt["commands"]):
            for channel in ("stdout","stderr"):
                expected=command[channel]
                path=jobdir/(str(i)+"."+channel+".log")
                assert path.stat().st_size==expected["bytes"] and sha(path)==expected["sha256"], str(path)
                evidence_files.append(path)
            commands.append({"index":i,"executable":command["executable"],"args":command["args"],
                             "exit_code":command["exitCode"],"project_command_started":command.get("projectCommandStarted"),
                             "network":command.get("network")})
        jobs.append({"task_id":receipt["taskId"],"job_id":job_id,"status":receipt["status"],
                     "receipt_path":str(receipt_path.relative_to(ROOT)).replace("\\","/"),
                     "receipt_sha256":sha(receipt_path),"commands":commands})
    write(BASE/"native-evidence-verified.json",jsontext({"schema":"master-native-inspection/v1",
          "meaning":"Workspace inspection copies checked against their receipt log bindings; server-owned originals remain authoritative.",
          "jobs":jobs}))
    summary=f"""# SoccerMaster master implementation candidate — 13 September 2026

Internal, unpromoted, awaiting independent audit. **SYSTEMS GO / SEMANTIC NO-GO.**

1. The local implementation package is reviewable. Full verification passed **{full_count} tests** and all six required project scripts; reset was preview only. Both finite literal and local query-model rehearsals passed 23 systems checks. The exact receipts and source identities are in [the index](../../artifacts/master-package-20260913/master-evidence-index.json).
2. The official SoccerMaster metadata preflight and raw adapter contracts are implemented, with 55 focused tests. The actual inventory is BLOCKED on {len(preflight['blockers'])} explicit reasons, including missing supplied source/checkpoints, PyTorch/Transformers, bound approvals, official callable/normalization, ontology reconciliation and measured peak memory. No official model was imported or executed. Two 8 GiB GPUs do not prove fit.
3. The frozen general-video path now has an explicit SoccerNet point-label converter, pre-inference label hash/scoring bindings, full redacted raw responses, immutable attempt history, deterministic one-to-one event/time scoring, explicit failure denominators and offline tests. The six-clip reproduction uses generated silent color screens and invented reports/labels: {repro['counts']['true_positive']} matched labels, {repro['counts']['false_positive']} unmatched predictions and {repro['counts']['false_negative']} missed labels. These are fixture arithmetic, not soccer performance. Twelve intake slots are unassigned; no actual Gemini benchmark has run.
4. [The coach packet v2](coach-discovery-master-v2-2026-09-13.md) contains five category hypotheses, five interaction modes, workflow questions, a scope rubric and an evidence-linked demo. No coach interview or usefulness validation occurred. Sketch/example/conversational features remain design or partial capabilities as labeled.
5. The two current local query-model calls completed but expanded ordinary questions into unrelated event types. The wrappers report latency_ms=0 rather than measured model latency; this remains an auditor-owned repair. The older long-form VLM package is not the official SoccerMaster checkpoint and its semantic failures remain evidence. No visual inference, new weights, independent annotation, calibration or population claim is made.
6. Company Runtime executed new bounded source-grounded work without replaying retained jobs or creating a scheduler. Its temporary 07:07–07:10 UTC interruption was coordinator maintenance. The saved planner traces expose invalid paths/envelopes and a possible absolute/relative recovery-source mismatch; autonomous planner recovery is not established by operator-directed native execution. The separate auditor must adjudicate exact evidence and any repairs before further promotion.

Read [the local runbook](../master-package-runbook-2026-09-13.md) for commands, label schema, limits and smallest gated next steps. The master index binds every candidate and validation output. The first baseline stopped on missing Git in the sandbox PATH; the corrected baseline passed 42 tests. A later attempted pre-fix test used a Python without pytest and is not counted as evidence of a failing regression. Both failures remain in native history, alongside any correctly labeled reconstructed regression.

Remaining hard gates: actual rights/processor and spend evidence; runtime credentials for any hosted call; supplied official source/checkpoint/license evidence and compatible dependencies; source/match-disjoint inputs and a frozen SoccerNet point-to-interval/ontology conversion; independent human annotation/adjudication; coach workflow validation; exact Luna review then Terra promotion; external sharing/publication authorization. Approval-file hashes authenticate content identity, not an issuer. Current source metadata is historical unless the separately captured source-watch receipt supplies a newer observation.
"""
    candidate=ROOT/"research/candidates/soccermaster-master-implementation-v1-2026-09-13.md"
    write(candidate,summary)
    oldcoach=ROOT/"research/candidates/coach-discovery-master-v1-2026-09-13.md"
    coach=oldcoach.read_text(encoding="utf-8").replace("Coach discovery master v1","Coach discovery master v2").replace("(/C:/","(C:/")
    supplement="""
## September 13 systems rehearsal supplement

This v2 preserves the v1 historical source table as creation-time evidence and adds fresh internal systems observations. The [literal rehearsal](../../artifacts/master-package-20260913/demo-v1/demo/receipt.json) and [local query-model rehearsal](../../artifacts/master-package-20260913/model-demo-v1/receipt.json) each passed 23 checks. Both finite servers shut down. No browser decoding observation was repeated on September 13; media byte ranges and timestamp bindings were checked.

The query model completed two text/ontology calls, but its [shot-query plan](../../artifacts/master-package-20260913/model-demo-v1/search-1.json) added stoppage, transition and offside, while its [cross-query plan](../../artifacts/master-package-20260913/model-demo-v1/search-2.json) added ball recovery and other unrelated types. A schema-valid plan and passing systems check are not faithful interpretation. Query latency is not measured by the current long-form wrappers (their field is hard-coded zero). Keep the literal-mode presentation available and inspect each returned claim against footage. This supplement is not coach validation or promotion.
"""
    coachpath=ROOT/"research/candidates/coach-discovery-master-v2-2026-09-13.md"
    write(coachpath,coach+supplement)
    marker="## September 13 master implementation and audit handoff"
    paragraph=f"""
{marker}

Internal candidate: research/candidates/soccermaster-master-implementation-v1-2026-09-13.md. Exact source/native log identities: artifacts/master-package-20260913/master-evidence-index.json and native-evidence-verified.json. Full native validation: {full_count} tests, six required scripts successful, preview-only reset, {verification['frozen_file_count']} named pilot files unchanged. Fresh finite literal and local query-model demos each passed 23 systems checks; query expansion remains semantically unreliable and latency reporting is unmeasured. Official preflight is BLOCKED with {len(preflight['blockers'])} exact reasons, no inference/downloads. Six generated color-screen clips exercise frozen label hashing, raw/resume/seals and descriptive scoring; no actual Gemini or official-checkpoint result is claimed.

Next: independent audit and substantiated repairs; then exact Luna/Terra promotion sequence for shareable material. Acquire nothing and contact nobody without existing gates. Actual clip enrollment, rights/processor/spend evidence, compatible official assets/dependencies, adoption of a frozen point-label policy, match isolation, independent annotation/adjudication and coach workflow remain open. Company Runtime recovered retained native execution following coordinator maintenance; invalid autonomous planner envelopes and source-path matching remain distinct unresolved evidence. No scheduler, job replay, commit/push, public sharing, cloud video call or trained-weight improvement occurred.
"""
    changed=[]
    for rel in ("research/action-plan.md","research/decision-log.md","RUN_LOG.md","research/paper-outline.md"):
        path=ROOT/rel
        before=sha(path)
        text=path.read_text(encoding="utf-8-sig")
        assert marker not in text
        path.write_text(text.rstrip()+"\n"+paragraph,encoding="utf-8",newline="\n")
        changed.append({"path":rel,"before_sha256":before,"after_sha256":sha(path)})
    ledger=ROOT/"research/archit-lucas-requirements-and-radar.md"
    text=ledger.read_text(encoding="utf-8-sig")
    before=sha(ledger)
    assert marker not in text
    text=text.replace("Updated: 2026-09-08 UTC","Updated: 2026-09-13 UTC",1)
    note="""
## September 13 current coverage reconciliation

This receipt-backed reconciliation supersedes older operational statuses below; historical evidence remains retained. Implementation is awaiting independent audit and is not promoted.

| Requirement group | Current disposition and next evidence |
| --- | --- |
| Archit progress document / publication | New local master and coach candidates exist; scheduled publication stays PAUSED. No OAuth or Google publication claim added. |
| College technology / workflow | Prior landscape remains internal source work; real Maryland/Georgetown workflow, export and unmet need remain unverified. |
| Measurable improvement / local models / GPT reasoning | New scoring and preservation tests plus two actual query-model calls; unrelated event expansion persists. No weight, visual-accuracy or frontier-parity improvement. |
| Gemini minimum 6 / target 10–15 | Frozen harness, scorer and six-color-screen reproduction implemented. Twelve intake slots are unassigned; actual rights-safe enrollment, credentials/spend evidence and real inference remain gated. |
| Official SoccerMaster same clips | Offline preflight/raw adapter implemented and tested; actual inventory BLOCKED. Official source/checkpoints/dependencies/callable/ontology/compute remain unresolved. No model execution. |
| Five clip categories / five interactions | Coach v2 contains hypotheses, implementation status, workflow questions and sport-scope rubric; no coach validation or new sketch/example interface. |
| Evidence-linked demo | Literal and local query-model modes each passed 23 fresh systems checks with finite shutdown. No fresh browser-decoder observation; semantic quality and model latency not established. |
| Commentary / failure-aware evaluation | Labels stay posthoc and hash-frozen; commentary excluded from scoring; failed requests/abstentions retained. Human independence, adoption of a reviewed point-label policy and scientific validation remain open. |
| Old SSD / protected directories | Existing consolidation evidence and protected-directory caveat unchanged; no ACL, credential or media-rights change. |
| Current research radar | Project and paper source-watch receipts observed September 13 and retained in runtime-observation.json. Repository/checkpoint snapshots in preflight are historical; no new release or local reproduction claim. |
| Efficient agents / final UMD-publication package | Concrete native code/test/demo receipts supersede note-only progress. Invalid planner recovery is not declared fixed. Separate independent audit pending; Luna/Terra and protected release gates remain. |

"""
    first=text.find("## Goal")
    text=text[:first]+note+text[first:]
    ledger.write_text(text.rstrip()+"\n"+paragraph,encoding="utf-8",newline="\n")
    changed.append({"path":str(ledger.relative_to(ROOT)),"before_sha256":before,"after_sha256":sha(ledger)})
    statepath=ROOT/"state/loop-state.json"
    before=sha(statepath)
    state=read(statepath)
    state["updatedAt"]=datetime.now(timezone.utc).isoformat()
    state["masterPackage20260913"]={"status":"implementation_ready_awaiting_independent_audit",
       "candidate":str(candidate.relative_to(ROOT)).replace("\\","/"),
       "evidenceIndex":"artifacts/master-package-20260913/master-evidence-index.json",
       "fullTestsPassed":full_count,"requiredScriptsPassed":6,"literalDemoChecks":23,"queryModelDemoChecks":23,
       "queryModelSemanticReliability":False,"queryLatencyMeasured":False,"officialSoccerMasterExecuted":False,
       "geminiVideoExecuted":False,"syntheticReproductionClips":6,"actualBenchmarkClipsEnrolled":0,
       "coachValidation":False,"scientificValidation":False,"shareableCandidatePromoted":False,
       "autonomousPlannerRecoveryAccepted":False,"schedulerCreated":False,"retainedJobsReplayed":False}
    state["completedUnit"]="September 13 local master implementation and systems evidence are ready for independent audit; see masterPackage20260913. SYSTEMS GO / SEMANTIC NO-GO. Official checkpoint and actual hosted benchmark remain gated."
    state["evidencePaths"]=list(dict.fromkeys(state.get("evidencePaths",[])+[
       "artifacts/master-package-20260913/master-evidence-index.json",
       "artifacts/master-package-20260913/native-evidence-verified.json",
       str(preflight_path.relative_to(ROOT)).replace("\\","/"),
       str(repro_path.relative_to(ROOT)).replace("\\","/")]))
    statepath.write_text(jsontext(state),encoding="utf-8",newline="\n")
    changed.append({"path":"state/loop-state.json","before_sha256":before,"after_sha256":sha(statepath)})
    write(BASE/"documentation-update-receipt.json",jsontext({"changes":changed,"promoted":False}))
    sources=["prototype/hosted_video_label_conversion.py","tests/test_hosted_video_label_conversion.py","scripts/verify-master-package.py","scripts/build-master-package.py","scripts/reproduce-hosted-video-scoring.py",
      "prototype/hosted_video_benchmark.py","prototype/hosted_video_scoring.py","prototype/soccermaster_preflight.py",
      "prototype/coach-event-report.prompt.txt","prototype/coach-event-report.schema.json",
      "tests/test_hosted_video_benchmark.py","tests/test_hosted_video_scoring.py","tests/test_soccermaster_preflight.py",
      "research/fixtures/soccermaster-official-preflight-v1.json","research/fixtures/general-video-clip-intake-template-v1.json",
      "research/master-package-runbook-2026-09-13.md",
      "research/candidates/coach-discovery-master-v1-2026-09-13.md",
      "research/candidates/coach-discovery-master-v2-2026-09-13.md",
      "research/candidates/soccermaster-master-implementation-v1-2026-09-13.md",
      "research/action-plan.md","research/decision-log.md","research/archit-lucas-requirements-and-radar.md",
      "research/paper-outline.md","RUN_LOG.md","state/loop-state.json"]
    files=set(ROOT/x for x in sources)
    files.update(evidence_files)
    files.add(preflight_path)
    files.update(p for p in BASE.rglob("*") if p.is_file())
    files.update(p for p in reproduction.rglob("*") if p.is_file())
    files.update(p for p in (ROOT/"data/private/hosted-video-label-conversion-20260913-v1").rglob("*.json") if p.is_file())
    files.update(p for p in (ROOT/"data/private/hosted-video-label-conversion-20260913-v2").rglob("*.json") if p.is_file())
    index={"schema":"soccermaster-master-evidence-index/v1","generated_at":datetime.now(timezone.utc).isoformat(),
       "status":"awaiting_independent_audit","scientific_validation":False,"promoted":False,
       "full_tests_passed":full_count,"native_jobs":[{"task_id":j["task_id"],"job_id":j["job_id"],"status":j["status"]} for j in jobs],
       "files":[{"path":str(q.relative_to(ROOT)).replace("\\","/"),"bytes":q.stat().st_size,"sha256":sha(q)} for q in sorted(files)]}
    write(BASE/"master-evidence-index.json",jsontext(index))
    print(json.dumps({"full_tests_passed":full_count,"files_indexed":len(index["files"]),
       "index_sha256":sha(BASE/"master-evidence-index.json"),"candidate_sha256":sha(candidate),"promoted":False}))
if __name__=="__main__": main()
