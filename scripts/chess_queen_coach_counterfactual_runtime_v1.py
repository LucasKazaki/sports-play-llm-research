"""Thin fixed-selected64 warm start over the exact qualified v2 runtime."""
from pathlib import Path
from chess_queen_coach_sft_runtime_v2 import Runtime as QualifiedRuntime,checked

CANDIDATE='queen-pawn-8/nf4-coach-counterfactual-v1'


def validate_start(identity):
    if(identity.get('step')!=64 or identity.get('parameter_count')!=1916928
        or identity.get('sha256')!='73e632f65d9146c789223ddcd7cbe106041b84aecab25ed9a775efc11bb28e3e'
        or identity.get('candidate_id')!='queen-pawn-8/nf4-coach-sft-v2'):
        raise ValueError('Exact prior selected64 warm start required')
    if checked.nf4.base.digest(Path(identity['path']))!=identity['sha256']:raise ValueError('Warm-start checkpoint bytes changed')


class Runtime(QualifiedRuntime):
    def load(self):
        if self.model is not None:return
        validate_start(self.plan['warm_start'])
        super().load() # Same NF4/LC0/bridges/zero-B insertion and manual checkpoint path.
        self.load_adapter(self.plan['warm_start']) # Strict144FP32 keys/shapes/finite values and actual CUDA copy.
        self.warm_start_effective_hash=checked.streamed_hash(self.torch,self.parameters,self.guard)

    def save_adapter(self,directory,step,presentations):
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);path=directory/'adapter.pt'
        self.torch.save({name:value.detach().cpu()for name,value in self.parameters},path)
        identity={'path':str(path.resolve()).replace('\\','/'),'sha256':checked.nf4.base.digest(path),
            'step':step,'presentations':presentations,'parent_presentations':512,'parameter_count':1916928,
            'candidate_id':CANDIDATE,'source_sha256':checked.nf4.base.digest(Path(__file__)),
            'warm_start':self.plan['warm_start'],'warm_start_effective_hash':self.warm_start_effective_hash}
        checked.nf4.save(directory/'metadata.json',identity);return identity

    def infer(self,row,identity):
        value=super().infer(row,identity)
        value.update(schema='chess.queen-coach-counterfactual-output.v1',candidate_id=CANDIDATE,
            qualified_runtime_source_sha256=value['adapter_sha256'],
            adapter_sha256=checked.nf4.base.digest(Path(__file__)),warm_start=self.plan['warm_start'])
        return value
