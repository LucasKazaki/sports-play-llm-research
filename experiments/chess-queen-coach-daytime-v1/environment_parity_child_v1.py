"""Authored environment metadata only; no framework or model imports."""
import argparse
import ctypes
from ctypes import wintypes as W
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import site
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from owned_worker_v2 import WindowsProof, PROFILE
PACKAGES = {'torch': 'torch', 'transformers': 'transformers', 'bitsandbytes': 'bitsandbytes',
    'peft': 'peft', 'chess': 'chess'}


def no_frameworks():
    forbidden = {'torch', 'transformers', 'bitsandbytes', 'peft', 'chess'}
    found = sorted(name for name in sys.modules if name.split('.')[0] in forbidden)
    if found: raise RuntimeError('Metadata payload imported a forbidden framework: '+','.join(found))


def package_metadata():
    values = {}
    for distribution, module in PACKAGES.items():
        spec = importlib.util.find_spec(module)  # Top-level lookup; no package execution.
        values[distribution] = {'version': importlib.metadata.version(distribution),
            'module_origin': spec.origin if spec else None,
            'module_search_locations': list(spec.submodule_search_locations or []) if spec else []}
    return values


def current_job_pids(api):
    capacity = 64
    while capacity <= 4096:
        buffer = ctypes.create_string_buffer(8+capacity*ctypes.sizeof(ctypes.c_size_t)); returned = W.DWORD()
        ctypes.set_last_error(0)
        ok = api.k.QueryInformationJobObject(None, 3, buffer, len(buffer), ctypes.byref(returned))
        code = ctypes.get_last_error(); assigned = ctypes.c_uint32.from_buffer(buffer, 0).value
        count = ctypes.c_uint32.from_buffer(buffer, 4).value
        if not ok and code != 234: raise ctypes.WinError(code)
        if not ok or count < assigned: capacity *= 2; continue
        if count != assigned or count > capacity or returned.value < 8+count*ctypes.sizeof(ctypes.c_size_t):
            raise ValueError('Incomplete immediate-job list')
        values = list((ctypes.c_size_t*count).from_buffer(buffer, 8))
        if len(set(values)) != count or any(pid <= 0 for pid in values): raise ValueError('Invalid immediate-job list')
        return sorted(values)
    raise ValueError('Immediate-job list exceeds4096')


def collect():
    no_frameworks(); api = WindowsProof(); packages = package_metadata(); no_frameworks()
    return {'status': 'completed', 'schema': 'chess.environment-parity-child.v1',
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'environment': {'sys_executable': sys.executable, 'base_executable': sys._base_executable,
            'prefix': sys.prefix, 'base_prefix': sys.base_prefix, 'exec_prefix': sys.exec_prefix,
            'base_exec_prefix': sys.base_exec_prefix, 'sys_path': list(sys.path),
            'site': {'site_packages': site.getsitepackages(), 'user_site_packages': site.getusersitepackages(),
                'enable_user_site': site.ENABLE_USER_SITE},
            'python_version': sys.version, 'version_info': list(sys.version_info),
            'flags': {name: getattr(sys.flags, name) for name in dir(sys.flags)
                if not name.startswith('_') and type(getattr(sys.flags, name)) in (int, bool)},
            'packages': packages},
        'topology': {'pid': os.getpid(), 'parent_pid': os.getppid(),
            'actual_process': api.identity(api.k.GetCurrentProcess()),
            'immediate_current_job_pids': current_job_pids(api), 'sys_orig_argv': sys.orig_argv},
        'model_calls': 0, 'engine_calls': 0, 'forbidden_framework_modules_imported': []}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True); args = parser.parse_args()
    result = collect()
    with args.out.open('x', encoding='utf-8') as handle: json.dump(result, handle, indent=2)
