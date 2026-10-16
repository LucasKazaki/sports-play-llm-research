"""Positive metadata projection and exact safe-source copies. No raw case reads."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
TASK=Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look')
AUDIT=TASK/'work/queen-review/coach-heldout-v2-failure-closed-review.json'
AUDIT_SHA='40cf8ac906ab2543a6768e438c4043fb313aa8f495927f4ad578f5414efeb4c9'
SNAP=TASK/'work/queen-coach-heldout-v2-source-1'

def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):value.update(chunk)
    return value.hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(value,indent=2)+'\n')
def info(path):return {'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)}
def exact(source,target,expected):
    assert sha(source)==expected and not target.exists()
    shutil.copyfile(source,target)
    assert target.read_bytes()==source.read_bytes() and sha(target)==expected
    return {'source':info(source),'copy':str(target.relative_to(HERE)),'sha256':sha(target),'bytes':target.stat().st_size,'kind':'exact_copy'}
def fields(value,names):return {name:value[name] for name in names}


def main():
    assert sha(AUDIT)==AUDIT_SHA
    audit=read(AUDIT);assert audit['status']=='passed_failure_accounting_not_a_completed_quality_evaluation'
    d=audit['denominators'];p=audit['provenance'];disc=audit['review_disclosure']
    assert d['planned']==64 and d['baseline']=={'completed':28,'partial':2,'failed':1,'not_run':1}
    assert d['selected']=={'not_run':32} and d['not_run_total']==33 and d['unknown_after_interruption']==0
    assert p['baseline_actual_step']==0 and p['selected_step64_planned_but_not_loaded_or_called'] is True
    assert disc['new_counterfactual_data_design_protocol_frozen_before_exposure'] is True
    assert disc['new_counterfactual_intake_excludes_all_old512_reserved_games'] is True
    assert disc['held_references_or_scores_opened'] is False and disc['raw_prose_quality_scored'] is False
    r=audit['resource_checks'];m=audit['memory']
    projection={'schema':'chess.coach-heldout-v2-public-failure-projection.v1',
        'status':'closed_failed_incomplete_quality_evaluation','projected_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_audit':info(AUDIT),'audit_verdict':audit['status'],
        'denominators':{'planned':64,'baseline':dict(d['baseline']),
            'selected':{'completed':0,'partial':0,'failed':0,'not_run':32},
            'total':{'completed':28,'partial':2,'failed':1,'not_run':33},
            'raw_receipts':31,'unknown_after_interruption':0,
            'completed_definition':'Returned EOS only; no correctness or coaching-quality meaning.'},
        'provenance':fields(p,('all_31_raw_input_packet_prompt_source_settings_inventory_and_checkpoint_bindings_match',
            'all_31_response_bytes_match_full_ledger','all_8_execution_snapshots_match_current_and_manifest',
            'baseline_actual_step','selected_step64_planned_but_not_loaded_or_called',
            'both_32_row_conditions_prewritten_before_setup_by_frozen_source',
            'transient_call_started_intents_are_panel_overwrites_not_an_append_only_call_journal',
            'worker_arguments_sha256','frozen_protocol_sha256','selection_sha256','no_postrun_frozen_storage_verification')),
        'resources':fields(r,('samples','journal_equals_final_resource_array','start_available','last_available',
            'running_floors','physical_min_bytes','gpu_free_min_bytes')),
        'memory_observations':{'events':m['events'],'completed_cleanup_boundaries':m['completed_cleanup_boundaries'],
            'unchanged_live_cuda_allocation_across_each_cleanup':m['unchanged_live_cuda_allocation_across_each_cleanup'],
            'failed_request_has_no_returned_generation_cleanup':m['failed_request_has_no_returned_generation_cleanup'],
            'growth':fields(m['growth'],('cleanup_post_private_start_bytes','cleanup_post_private_last_bytes',
                'cleanup_post_private_delta_bytes','global_commit_delta_first_to_failure_bytes',
                'private_last_observation_seconds_before_failure'))},
        'interpretation':'The recorded stop is a global commit-headroom reserve breach. Different process/global counters, sparse process samples and stable live CUDA storage do not identify an exclusive cause, prove a leak or establish a guaranteed repair. No completed matched comparison or quality result.',
        'exposure_disclosure':{'auditor_parsed_raw_JSON_for_metadata':disc['raw_JSON_files_parsed_for_metadata'],
            'accidental_display':'An earlier baseline decoded response was displayed, as were the failed response empty text field and token IDs. None of that content is reproduced here.',
            'semantic_analysis_or_prose_scoring_performed':False,'held_references_or_scores_opened':False,
            'correction':'Subsequent audit reads used a positive metadata allowlist.',
            'root_observation':'Root reports seeing no decoded prose.',
            'not_a_zero_raw_exposure_phase':True,
            'successor_source_design_frozen_before_exposure':True,
            'successor_intake_excludes_all_prior_reserved_games':512},
        'disposition':{'same_held_case_retry_authorized':False,'trained_tutor_profile_eligible':False,
            'selected_panel_actual_calls':0,'quality_metrics_published':False,
            'future_work':'Separate pre-frozen source-disjoint cohort and independent corpus/source review; no silent retry, case substitution or current-protocol change.'},
        'packaging_scope':{'current_held_raw_input_reference_files_opened':0,'model_engine_GPU_calls':0,
            'complete_audit_copied':False,'per_case_metadata_copied':False,'raw_prose_or_token_content_copied':False}}
    save(HERE/'summary.json',projection)
    copies=[]
    items=[(ROOT/'data/private/chess-queen-coach-sft-training-v2/heldout-1-worker.json','worker.json',
        'f443d8fa2ac23a38477413528949f086d27432523fb25b1a81910574ebd5dd60'),
        (ROOT/'data/private/chess-queen-coach-sft-training-v2/heldout-1/failure.json','failure.json',
        '5fc258eec94a03128453121ec8c38a4a0a301c6cfd7c1c737e3f2c5df333b2ab'),
        (TASK/'work/overnight/coach-held-failure-owner-closed.json','owner-closure.json',
        'e7777a4a59004c8df9031d446e6d925527c0f86e3c4ddaacbb323a6758582526'),
        (SNAP/'manifest.json','execution-snapshot-manifest.json',
        'c3633d7e2e9ccee84537e7c82d65f73f733d0eb9347362d38172fa19063211f8')]
    # These are exact already-audited metadata receipts, not arbitrary raw files.
    allowed_metadata_keys=[set(audit['worker']),{'status','error','planned_responses'},
        {'schema','observed_at','worker','worker_sha256','worker_status','exit_code','child_pid',
         'child_pid_absent_OpenProcess_error','child_exited_before_lease_release','lease_probe_free','CPU_samples','GPU_model_calls','claim'},
        {'schema','prepared_at','status','selected_step','selection_sha256','protocol_sha256','worker_receipt','output',
         'maximum_seconds','target_arguments','expected_worker_arguments_sha256','planned_calls','baseline_calls',
         'selected_calls','learned_calls_already_spent','held_reference_semantic_read','snapshots','cutoff_utc','no_retry'}]
    for (source,name,expected),keys in zip(items,allowed_metadata_keys):
        assert set(read(source))==keys
        copies.append(exact(source,HERE/name,expected))
    source_dir=HERE/'source';source_dir.mkdir()
    names={'chess_queen_coach_sft_train_v2.py','chess_queen_coach_sft_runtime_v2.py',
        'chess_queen_coach_sft_eval_v1.py','chess_queen_nf4_adapter_v2.py','gpu_worker.py',
        'test_chess_queen_coach_sft_train_v2.py'}
    records=read(SNAP/'manifest.json')['snapshots'];assert len(records)==8
    hashed_only=[];seen=set()
    for row in records:
        original=(ROOT/row['original']).resolve();source=SNAP/row['snapshot']
        assert original.is_relative_to(ROOT) and source.parent==SNAP
        assert sha(original)==sha(source)==row['sha256'] and source.stat().st_size==row['bytes']
        if row['snapshot'] in names:
            copies.append(exact(source,source_dir/row['snapshot'],row['sha256']));seen.add(row['snapshot'])
        else:
            assert row['snapshot'] in {'protocol.json','selection.json'}
            hashed_only.append({'snapshot':row['snapshot'],'original':row['original'],'sha256':row['sha256'],
                'bytes':row['bytes'],'copy_published':False,
                'reason':'Contains development group identities or development-selection quality fields; hash-only in this failure package.'})
    assert seen==names
    manifest={'schema':'chess.coach-heldout-v2-public-failure-manifest.v1','status':'prepared_for_root_review',
        'source_audit':info(AUDIT),'exact_copies':copies,'hash_only_execution_snapshots':hashed_only,
        'all_8_source_snapshots_verified':True,'derived_files':[info(HERE/name) for name in ('summary.json','README.md','prepare_public.py')],
        'not_published':['held response/input/reference data','per-case IDs and status records','raw prose and token arrays',
            'complete private audit','quality metrics','weights','held worker log'],
        'no_frozen_TRAIN_copy_edits':True,'model_engine_GPU_calls':0,'new_held_raw_content_reads':0}
    save(HERE/'evidence-manifest.json',manifest)
    print(json.dumps({'manifest':info(HERE/'evidence-manifest.json'),'summary':info(HERE/'summary.json'),
        'exact_copies':len(copies),'code_test_copies':len(names),'hash_only_snapshots':len(hashed_only)},indent=2))


if __name__=='__main__':main()
