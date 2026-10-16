"""Metadata-only pre-intake amendment isolating the already reviewed loader."""
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function_tree(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'materialize_pinned_module')
    return ast.dump(function, annotate_fields=True, include_attributes=False)


adapter = ROOT / 'scripts/chess_queen_adapter.py'
helper = ROOT / 'scripts/chess_queen_materialize.py'
left, right = function_tree(adapter), function_tree(helper)
if left != right:
    raise ValueError('Isolated helper differs from reviewed function')
receipt = {'status': 'exact_function_ast_equivalence', 'comparison': 'Full function including signature, docstring and body; location attributes excluded',
    'adapter_path': str(adapter.relative_to(ROOT)), 'adapter_sha256': digest(adapter),
    'helper_path': str(helper.relative_to(ROOT)), 'helper_sha256': digest(helper),
    'function_ast_sha256': hashlib.sha256(right.encode()).hexdigest(), 'model_calls': 0}
(HERE / 'materialize-equivalence.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
original = HERE / 'protocol.json'
plan = copy.deepcopy(json.loads(original.read_text(encoding='utf-8')))
plan['implementation_sha256'] = digest(ROOT / 'scripts/chess_encoder_check_v1.py')
plan['frozen_at'] = datetime.now(timezone.utc).isoformat()
plan['dependencies'] = [{**item, 'sha256': digest(ROOT / item['path'])} for item in plan['dependencies']
                        if item['path'] != 'scripts/chess_queen_adapter.py']
plan['dependencies'].extend({'path': path, 'sha256': digest(ROOT / path)} for path in
    ('scripts/chess_queen_materialize.py', 'tests/test_chess_queen_materialize.py'))
plan['pre_intake_amendment'] = {'original_protocol_sha256': digest(original),
    'reason': 'Decouple the exact reviewed target-only loader from decoder adapter source churn. Original protocol never ran intake or model calls. Scientific method, data quotas, exclusion bindings, architecture, objective and selection unchanged.',
    'function_equivalence_sha256': digest(HERE / 'materialize-equivalence.json')}
target = HERE / 'protocol-v2.json'
with target.open('x', encoding='utf-8') as stream:
    json.dump(plan, stream, indent=2, allow_nan=False); stream.write('\n')
print(json.dumps({'protocol_sha256': digest(target), 'implementation_sha256': plan['implementation_sha256'],
    'helper_sha256': digest(helper), 'equivalence': receipt['function_ast_sha256']}))
