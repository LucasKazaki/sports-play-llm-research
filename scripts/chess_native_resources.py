"""Read-only Windows/GPU samples and a pure guard for one caller-owned request.

This module has no inference, unload, process-control, or configuration API.
The controller supplies a cancellation callback for its own HTTP connection.
"""
from dataclasses import asdict, dataclass
import csv
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import io
import math
import subprocess
import sys

GIB=1024**3

@dataclass(frozen=True)
class Sample:
    physical_total_bytes: int
    physical_available_bytes: int
    commit_limit_bytes: int
    commit_total_bytes: int
    gpu_total_bytes: int
    gpu_free_bytes: int
    utc: str = ''

    @property
    def commit_headroom_bytes(self): return self.commit_limit_bytes-self.commit_total_bytes

    def validate(self):
        for name,value in asdict(self).items():
            if name!='utc' and (type(value) is not int or value<0):
                raise ValueError('missing/noninteger/nonfinite resource counter: '+name)
        if not (0<self.physical_total_bytes and self.physical_available_bytes<=self.physical_total_bytes):
            raise ValueError('invalid physical counters')
        if not (0<self.commit_limit_bytes and self.commit_total_bytes<=self.commit_limit_bytes):
            raise ValueError('invalid commit counters')
        if not (0<self.gpu_total_bytes and self.gpu_free_bytes<=self.gpu_total_bytes):
            raise ValueError('invalid GPU counters')

@dataclass(frozen=True)
class Policy:
    start_physical_available_bytes: int = 10*GIB
    start_commit_headroom_bytes: int = 16*GIB
    start_gpu_free_bytes: int = 13*GIB
    stop_physical_available_bytes: int = 4*GIB
    stop_commit_headroom_bytes: int = 8*GIB
    stop_gpu_free_bytes: int = GIB
    maximum_owned_request_seconds: float = 120.
    maximum_sample_gap_seconds: float = 3.

def reasons(sample,policy,stage):
    if stage not in ('start','running'): raise ValueError('invalid stage')
    try: sample.validate()
    except (ValueError,TypeError,AttributeError): return ['invalid_or_missing_sample']
    prefix='start_' if stage=='start' else 'stop_'
    values=(('physical_available_bytes',sample.physical_available_bytes),
            ('commit_headroom_bytes',sample.commit_headroom_bytes),('gpu_free_bytes',sample.gpu_free_bytes))
    return [name+'_below_reserve' for name,value in values if value<getattr(policy,prefix+name)]

class OwnedGuard:
    """Latching guard; cancellation is limited to the injected owned callback."""
    def __init__(self,cancel_owned,policy=Policy()):
        self.cancel_owned=cancel_owned; self.policy=policy
        self.started=False; self.active=False; self.cancelled=False; self.reason=[]
        self.start_time=None; self.last_sample_time=None

    def begin(self,sample,monotonic):
        if self.started: raise ValueError('one request only; guard cannot be replayed')
        if not math.isfinite(monotonic): raise ValueError('invalid monotonic clock')
        self.started=True
        self.reason=reasons(sample,self.policy,'start')
        if self.reason: return False
        self.active=True; self.start_time=self.last_sample_time=monotonic
        return True

    def observe(self,sample,monotonic):
        if not self.active: return self.reason
        issues=[]
        if not math.isfinite(monotonic) or monotonic<self.last_sample_time:
            issues.append('invalid_monotonic_clock')
        else:
            if monotonic-self.last_sample_time>self.policy.maximum_sample_gap_seconds: issues.append('monitor_sample_gap')
            if monotonic-self.start_time>=self.policy.maximum_owned_request_seconds: issues.append('owned_request_deadline')
            self.last_sample_time=monotonic
        issues.extend(reasons(sample,self.policy,'running'))
        if issues:
            self.reason=issues; self.active=False; self.cancelled=True
            self.cancel_owned()  # Exactly once, even if the owned callback raises.
        return self.reason

    def finish(self): self.active=False

def windows_sample():
    """Query only system counters and one NVIDIA GPU, without loading a model."""
    if sys.platform!='win32': raise OSError('Windows-only sampler')
    class Info(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),
                  *[(name,ctypes.c_size_t) for name in ('CommitTotal','CommitLimit','CommitPeak',
                    'PhysicalTotal','PhysicalAvailable','SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')],
                  ('HandleCount',wintypes.DWORD),('ProcessCount',wintypes.DWORD),('ThreadCount',wintypes.DWORD)]
    info=Info(); info.cb=ctypes.sizeof(info)
    api=ctypes.WinDLL('psapi',use_last_error=True).GetPerformanceInfo
    api.argtypes=(ctypes.POINTER(Info),wintypes.DWORD); api.restype=wintypes.BOOL
    if not api(ctypes.byref(info),info.cb): raise ctypes.WinError(ctypes.get_last_error())
    data=subprocess.run(['nvidia-smi','--query-gpu=memory.total,memory.free','--format=csv,noheader,nounits'],
                        check=True,capture_output=True,text=True,timeout=2)
    rows=list(csv.reader(io.StringIO(data.stdout)))
    if len(rows)!=1 or len(rows[0])!=2: raise ValueError('single GPU numeric sample required')
    total,free=(int(x.strip())*1024**2 for x in rows[0])
    sample=Sample(info.PhysicalTotal*info.PageSize,info.PhysicalAvailable*info.PageSize,
                  info.CommitLimit*info.PageSize,info.CommitTotal*info.PageSize,total,free,
                  datetime.now(timezone.utc).isoformat())
    sample.validate()
    return sample
