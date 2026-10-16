"""Small source/math probe; never import Torch or run a model/kernel."""
import ast
import copy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(r"C:/Users/lucas/Documents/Codex/2026-10-15/go/work/repos/sports-play-llm-research")
OUT=Path(__file__).with_name('source-math-result.json')
source=ROOT/'.venv-soccernet/Lib/site-packages/bitsandbytes/backends/cuda/ops.py'
tree=ast.parse(source.read_text())
function=next(node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name=='_gemm_4bit_use_custom_cuda')
body_sha=hashlib.sha256(ast.dump(function,include_attributes=False).encode()).hexdigest()
function=copy.deepcopy(function);function.decorator_list=[]
# This exact installed function contains only arithmetic/conditionals and one
# property callback. Stub device properties; do not import its package.
assert not any(isinstance(node,(ast.Import,ast.ImportFrom,ast.With,ast.Try))for node in ast.walk(function))
assert all(isinstance(node.func,ast.Name)and node.func.id=='_gpu_dispatch_props'for node in ast.walk(function)if isinstance(node,ast.Call))
namespace={'torch':SimpleNamespace(float32='float32',float16='float16'),
    '_GEMM_4BIT_CUSTOM_FLOOR_M':4,'_gpu_dispatch_props':lambda index:(84,12,0)}
exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(source),'exec'),namespace)
choose=namespace[function.name]
config=json.loads((ROOT/'data/private/chess-queen-v1/pawn-8/config.json').read_text())
h=config['hidden_size'];kv=config['num_key_value_heads']*(h//config['num_attention_heads']);inter=config['intermediate_size']
shapes={'q_proj':(h,h),'k_proj':(kv,h),'v_proj':(kv,h),'o_proj':(h,h),'gate_proj':(inter,h),'up_proj':(inter,h),'down_proj':(h,inter)}
dispatch=[{'module':name,'N':n,'K':k,'M':m,'use_custom_cuda':bool(choose(0,'bfloat16',m,n,k))}for name,(n,k)in shapes.items()for m in(1,84,85)]

def attention(query,keys,values,allowed):
    logits=[sum(a*b for a,b in zip(query,key))/math.sqrt(len(query))for key in keys]
    logits=[value if keep else-float('inf')for value,keep in zip(logits,allowed)]
    maximum=max(logits);weights=[math.exp(value-maximum)for value in logits];den=sum(weights)
    return sum(weight*value for weight,value in zip(weights,values))/den

query=[1.,.5];keys=[[1.,0.],[0.,1.],[1.,1.]];values=[10.,20.,30.]
full_last=[2>=key for key in range(3)];cached_correct=[True]*3;cached_wrong=[0>=key for key in range(3)]
full=attention(query,keys,values,full_last);cached=attention(query,keys,values,cached_correct);wrong=attention(query,keys,values,cached_wrong)
assert full==cached and abs(full-wrong)>1
assert list(range(85))[-1]==84 and [84][0]==84
result={'schema':'chess.cache-source-math-probe.v1','status':'passed','torch_imported':'torch'in sys.modules,
    'transformers_imported':'transformers'in sys.modules,'bitsandbytes_imported':'bitsandbytes'in sys.modules,
    'model_or_kernel_calls':0,'versions':{name:importlib.metadata.version(name)for name in('torch','transformers','bitsandbytes')},
    'bnb_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'dispatch_function_AST_sha256':body_sha,
    'authored_device_properties':{'multiprocessors':84,'major':12,'minor':0,'actual_hardware_query':False},
    'dispatch':dispatch,'mask_math':{'full_prefix_last_allowed':full_last,'cached_expected_allowed':cached_correct,
        'wrong_upper_left_q1_allowed':cached_wrong,'full_last_output':full,'cached_expected_output':cached,
        'wrong_upper_left_output':wrong,'position_offset_example':{'past_length':84,'new_position':84}},
    'limits':'Only source dispatch and mathematical mask geometry demonstrated. No actual BF16/NF4 numerical drift, hardware kernel, timing, accuracy or repair measured.'}
OUT.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
