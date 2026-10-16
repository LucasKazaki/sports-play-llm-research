"""Stable target-only storage helper, isolated from the evolving Queen decoder.

Function body is identical to the independently reviewed Queen adapter helper.
Importing this module never imports Torch, loads weights or allocates tensors.
"""
from pathlib import Path


def materialize_pinned_module(torch,factory,state_path,device,dtype):
    """Allocate only target storage; copy restricted mapped weights strictly.

    Meta initialization prevents a full temporary CPU FP32 random module. Set
    floating dtype while still meta, then allocate exactly the target tensors.
    assign=False preserves that device/dtype while copying the pinned values.
    """
    with torch.device('meta'):
        module=factory()
    module.to(dtype=dtype)
    module.to_empty(device=device)
    if Path(state_path).suffix=='.safetensors':
        from safetensors.torch import load_file
        state=load_file(str(state_path),device='cpu')
    else:
        state=torch.load(state_path,map_location='cpu',weights_only=True,mmap=True)
    module.load_state_dict(state,strict=True,assign=False)
    del state
    if any(tensor.is_meta for tensor in [*module.parameters(),*module.buffers()]):
        raise ValueError('Pinned module contains unmaterialized tensors.')
    return module
