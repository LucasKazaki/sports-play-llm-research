"""Training save provenance only; unchanged shared inference/loss/load implementations."""
from pathlib import Path
from chess_queen_coach_counterfactual_runtime_v1 import Runtime as Parent,checked,validate_start
CANDIDATE='queen-pawn-8/nf4-coach-conditional-line-v1'
class Runtime(Parent):
    def save_adapter(self,directory,step,presentations):
        identity=super().save_adapter(directory,step,presentations)
        identity.update(candidate_id=CANDIDATE,source_sha256=checked.nf4.base.digest(Path(__file__)),
            target_protocol=self.plan['target_export_protocol'],target_manifest=self.plan['corpus_manifest'],
            intervention='Conditional line target prose only; input/group/PV unchanged.')
        checked.nf4.save(Path(directory)/'metadata.json',identity)
        return identity
