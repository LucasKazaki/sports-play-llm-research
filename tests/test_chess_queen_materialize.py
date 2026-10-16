"""CPU contract tests for target-only materialization using tiny random fixtures."""
import ast
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chess_queen_materialize as stable


def tiny_fixture(torch, seen):
    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(2, 3))
            self.register_buffer('floating', torch.zeros(3, dtype=torch.float32))
            self.register_buffer('integer', torch.zeros(3, dtype=torch.int64))
            seen.append([t.is_meta for t in [*self.parameters(), *self.buffers()]])
    return Tiny


@pytest.mark.parametrize('suffix', ['.pt', '.safetensors'])
def test_meta_factory_allocates_no_cpu_random_model_and_values_dtypes_survive(tmp_path, suffix):
    torch = pytest.importorskip('torch')
    seen = []
    state = {'weight': torch.tensor([[1., 2., 3.], [4., 5., 6.]]),
             'floating': torch.tensor([.5, 1.5, 2.5]), 'integer': torch.tensor([1, 17, 2049])}
    path = tmp_path / ('tiny' + suffix)
    if suffix == '.pt':
        torch.save(state, path)
    else:
        from safetensors.torch import save_file
        save_file(state, str(path))
    model = stable.materialize_pinned_module(torch, tiny_fixture(torch, seen), path, 'cpu', torch.bfloat16)
    assert seen == [[True, True, True]]
    assert model.weight.dtype == model.floating.dtype == torch.bfloat16
    assert model.integer.dtype == torch.int64
    assert torch.equal(model.weight.float(), state['weight'])
    assert torch.equal(model.floating.float(), state['floating'])
    assert torch.equal(model.integer, state['integer'])
    assert all(not t.is_meta and t.device.type == 'cpu' for t in [*model.parameters(), *model.buffers()])


def test_missing_or_extra_state_keys_are_rejected_strictly(tmp_path):
    torch = pytest.importorskip('torch')
    path = tmp_path / 'missing.pt'; torch.save({'weight': torch.zeros(2, 3)}, path)
    with pytest.raises(RuntimeError, match='Missing key'):
        stable.materialize_pinned_module(torch, tiny_fixture(torch, []), path, 'cpu', torch.float32)
    path = tmp_path / 'extra.pt'
    torch.save({'weight': torch.zeros(2, 3), 'floating': torch.zeros(3),
                'integer': torch.zeros(3, dtype=torch.int64), 'unexpected': torch.zeros(1)}, path)
    with pytest.raises(RuntimeError, match='Unexpected key'):
        stable.materialize_pinned_module(torch, tiny_fixture(torch, []), path, 'cpu', torch.float32)


def test_stable_helper_import_has_no_backend_model_or_decoder_imports():
    tree = ast.parse(Path(stable.__file__).read_text())
    top_level_imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert len(top_level_imports) == 1 and isinstance(top_level_imports[0], ast.ImportFrom)
    assert top_level_imports[0].module == 'pathlib'
