"""Caller-local JSON persistence; bounded Windows sharing-denial replacement retry.

Only a closed, fully flushed unique temporary file can replace the destination.
Retry changes persistence timing, not the serialized value or model computation.
The failed temporary file remains available if a write/replacement fails.
"""
import json
import os
from pathlib import Path
import tempfile
import time

RETRY_SECONDS=.5
RETRY_INTERVAL_SECONDS=.02
MAXIMUM_ATTEMPTS=26
RETRYABLE_WINERRORS=frozenset((5,32,33))


def replace_closed(temporary,path,*,replace=None,monotonic=None,sleep=None):
    """Retry only the named Windows permission failures, retaining first error.

    The .5s wall bound includes replace calls but cannot interrupt a blocking OS
    call; it prevents another call/sleep after the deadline. The independent
    fixed-attempt bound also stops a nonadvancing clock in injected tests.
    """
    replace=os.replace if replace is None else replace
    monotonic=time.monotonic if monotonic is None else monotonic
    sleep=time.sleep if sleep is None else sleep
    started=monotonic();deadline=started+RETRY_SECONDS;first=None;attempts=0
    while True:
        if first is not None and(attempts>=MAXIMUM_ATTEMPTS or monotonic()>=deadline):
            first.add_note('Atomic JSON replacement exhausted bounded sharing-denial retry; '
                f'attempts={attempts}; temporary={temporary}; destination={path}')
            raise first
        attempts+=1
        try:
            replace(temporary,path)
            return
        except PermissionError as error:
            if getattr(error,'winerror',None)not in RETRYABLE_WINERRORS:raise
            if first is None:first=error
            remaining=deadline-monotonic()
            if remaining>0 and attempts<MAXIMUM_ATTEMPTS:
                sleep(min(RETRY_INTERVAL_SECONDS,remaining))


def save(path,value):
    """Same JSON value/indent/NaN rejection as prior save; close before replace."""
    path=Path(path)
    descriptor,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    temporary=Path(name)
    try:
        stream=os.fdopen(descriptor,'w',encoding='utf-8')
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    replace_closed(temporary,path)
