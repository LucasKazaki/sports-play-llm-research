"""Small CPU pre-GPU corpus/tokenizer contract; no backend imports."""


def verify_preflight(plan,bound,read):
    source=bound(plan['cpu_preflight_source'])
    actual=read(bound(plan['cpu_preflight']))
    if(actual.get('status')!='passed'or actual.get('cuda_initialized')is not False
        or actual.get('model_weights_loaded')is not False or actual.get('learned_forward_calls')!=0
        or actual.get('source_sha256')!=plan['cpu_preflight_source']['sha256']
        or actual.get('manifest_sha256')!=plan['corpus_manifest']['sha256']):
        raise ValueError('Actual fresh CPU-only tokenizer preflight required before GPU')
    for name,records,groups in[('train',1536,512),('development',96,32)]:
        value=actual.get('splits',{}).get(name,{})
        if(value.get('records')!=records or value.get('groups')!=groups
            or value.get('exact_integer_prefix_mask_eos_no_truncation')is not True
            or not 0<value.get('minimum_total_tokens',0)<=value.get('maximum_total_tokens',0)<=512
            or value.get('total_supervised_tokens',0)<=0):
            raise ValueError('CPU tokenizer complete TRAIN/dev quotas/context proof differs')
    return actual
