"""Observe and retain exact Windows Python child identities without importing Torch."""
from __future__ import annotations
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import sys
import time


def normalized(path):return os.path.normcase(os.path.abspath(path))


def validate(outer_pid,launcher,delegate,venv_image,base_image,require_job=True):
    """Pure topology contract. Identity observations come from retained OS handles."""
    if launcher['parent_pid']!=outer_pid or launcher['image']!=normalized(venv_image):
        raise ValueError('Launcher parent/image differs')
    if require_job and not launcher['in_job']:raise ValueError('Launcher not in inherited job')
    if delegate['pid']==launcher['pid']:
        if delegate!=launcher:raise ValueError('Direct identity changed')
        return 'direct'
    if(delegate['parent_pid']!=launcher['pid'] or delegate['image']!=normalized(base_image)
        or delegate['created']<launcher['created']):raise ValueError('Not exactly one known interpreter hop: '+repr({'launcher':launcher,'delegate':delegate,'expected_base':normalized(base_image)}))
    if require_job and not delegate['in_job']:raise ValueError('Delegate not in inherited job')
    return 'venv_redirector'


def validate_console(launcher,record,console_image,require_job):
    if(record['parent_pid']!=launcher['pid']or record['image']!=normalized(console_image)
        or record['created']<launcher['created']or(require_job and not record['in_job'])):
        raise ValueError('Unknown auxiliary console process')


class Windows:
    def __init__(self):
        if os.name!='nt':raise RuntimeError('Windows-only owned process observation')
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];self.k.CreateToolhelp32Snapshot.restype=W.HANDLE
        self.k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];self.k.OpenProcess.restype=W.HANDLE
        self.k.CloseHandle.argtypes=[W.HANDLE];self.k.CloseHandle.restype=W.BOOL
        self.k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)]
        self.k.QueryFullProcessImageNameW.restype=W.BOOL
        self.k.GetProcessTimes.argtypes=[W.HANDLE,*([ctypes.POINTER(W.FILETIME)]*4)];self.k.GetProcessTimes.restype=W.BOOL
        self.k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,ctypes.POINTER(W.BOOL)];self.k.IsProcessInJob.restype=W.BOOL
        self.k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];self.k.WaitForSingleObject.restype=W.DWORD
        self.k.TerminateProcess.argtypes=[W.HANDLE,W.UINT];self.k.TerminateProcess.restype=W.BOOL
        self.k.GetSystemDirectoryW.argtypes=[W.LPWSTR,W.UINT];self.k.GetSystemDirectoryW.restype=W.UINT
        class Entry(ctypes.Structure):
            _fields_=[('dwSize',W.DWORD),('cntUsage',W.DWORD),('th32ProcessID',W.DWORD),
                ('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',W.DWORD),('cntThreads',W.DWORD),
                ('th32ParentProcessID',W.DWORD),('pcPriClassBase',W.LONG),('dwFlags',W.DWORD),('szExeFile',W.WCHAR*260)]
        self.Entry=Entry
        for name in('Process32FirstW','Process32NextW'):
            method=getattr(self.k,name);method.argtypes=[W.HANDLE,ctypes.POINTER(Entry)];method.restype=W.BOOL

    def console_image(self):
        buffer=ctypes.create_unicode_buffer(32768);length=self.k.GetSystemDirectoryW(buffer,len(buffer))
        if not length or length>=len(buffer):raise ctypes.WinError(ctypes.get_last_error())
        return normalized(str(Path(buffer.value)/'conhost.exe'))

    def snapshot(self):
        handle=self.k.CreateToolhelp32Snapshot(2,0)
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        result={};entry=self.Entry();entry.dwSize=ctypes.sizeof(entry)
        try:
            more=self.k.Process32FirstW(handle,ctypes.byref(entry))
            while more:
                result[int(entry.th32ProcessID)]=int(entry.th32ParentProcessID)
                more=self.k.Process32NextW(handle,ctypes.byref(entry))
        finally:self.k.CloseHandle(handle)
        return result

    def retain(self,pid,parent):
        # TERMINATE is retained solely for this verified owned subtree's timeout.
        handle=self.k.OpenProcess(0x1000|0x100000|1,False,pid)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            buffer=ctypes.create_unicode_buffer(32768);size=W.DWORD(len(buffer))
            if not self.k.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)):raise ctypes.WinError(ctypes.get_last_error())
            times=[W.FILETIME()for _ in range(4)]
            if not self.k.GetProcessTimes(handle,*[ctypes.byref(value)for value in times]):raise ctypes.WinError(ctypes.get_last_error())
            job=W.BOOL()
            if not self.k.IsProcessInJob(handle,None,ctypes.byref(job)):raise ctypes.WinError(ctypes.get_last_error())
            return handle,{'pid':pid,'parent_pid':parent,'image':normalized(buffer.value),
                'created':(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime,'in_job':bool(job.value)}
        except BaseException:self.k.CloseHandle(handle);raise

    def exited(self,handle):
        value=self.k.WaitForSingleObject(handle,0)
        if value not in(0,258):raise ctypes.WinError(ctypes.get_last_error())
        return value==0


class Tracker:
    """A direct launcher and at most one observed known interpreter delegate."""
    def __init__(self,pid,outer_pid,require_job=True,venv_image=None,base_image=None,launcher_handle=None):
        self.os=Windows();self.outer=outer_pid;self.require_job=require_job
        self.venv=venv_image or sys.executable;self.base=base_image or sys._base_executable
        self.handles={};self.records={};self.delegate=None;self.auxiliary=None;self.console=self.os.console_image()
        parents=self.os.snapshot()
        if parents.get(pid)!=outer_pid:raise ValueError('Live launcher ancestry not observed')
        handle,record=self.os.retain(pid,outer_pid);self.handles[pid]=handle;self.records[pid]=record;self.launcher=record
        try:
            validate(outer_pid,record,record,self.venv,self.base,require_job)
            if launcher_handle is not None:
                times=[W.FILETIME()for _ in range(4)]
                if not self.os.k.GetProcessTimes(int(launcher_handle),*[ctypes.byref(value)for value in times]):
                    raise ctypes.WinError(ctypes.get_last_error())
                created=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
                if created!=record['created']:raise ValueError('Popen stable handle creation identity differs')
        except BaseException:self.close();raise

    def observe(self):
        parents=self.os.snapshot()
        for pid,parent in parents.items():
            if parent!=self.launcher['pid']or pid in self.records:continue
            handle,record=self.os.retain(pid,parent)
            try:
                if record['image']==self.console:
                    validate_console(self.launcher,record,self.console,self.require_job)
                    if self.auxiliary is not None:raise ValueError('Multiple console hosts')
                    self.auxiliary=record
                else:
                    validate(self.outer,self.launcher,record,self.venv,self.base,self.require_job)
                    if self.delegate is not None:raise ValueError('Multiple interpreter delegates')
                    self.delegate=record
            except BaseException:self.os.k.CloseHandle(handle);raise
            self.handles[pid]=handle;self.records[pid]=record
        # A second interpreter hop is never admitted.
        if any(parent in self.records and parent!=self.launcher['pid']for parent in parents.values()):
            raise ValueError('Extra descendant hop is forbidden')

    def proof(self,receipt):
        candidate=self.records.get(receipt.get('pid'))
        if candidate is None or candidate['parent_pid']!=receipt.get('parent_pid'):
            raise ValueError('Runtime receipt not bound to live observed identity')
        if candidate==getattr(self,'auxiliary',None):raise ValueError('Console host cannot be runtime')
        topology=validate(self.outer,self.launcher,candidate,self.venv,self.base,self.require_job)
        if self.delegate and candidate!=self.delegate:raise ValueError('Receipt omitted observed delegate')
        if not all(self.os.exited(handle)for handle in self.handles.values()):raise ValueError('Owned interpreter still live')
        return {'topology':topology,'runtime_pid':candidate['pid'],'runtime_parent_pid':candidate['parent_pid'],
            'launcher_pid':self.launcher['pid'],'observed_processes':list(self.records.values()),
            'all_observed_handles_exited':True,'job_membership_required':self.require_job}

    def terminate_owned(self):
        for pid in reversed(list(self.handles)):
            handle=self.handles[pid]
            if not self.os.exited(handle)and not self.os.k.TerminateProcess(handle,2):raise ctypes.WinError(ctypes.get_last_error())
        deadline=time.monotonic()+10
        while not all(self.os.exited(h)for h in self.handles.values()):
            if time.monotonic()>=deadline:raise RuntimeError('Owned interpreter exit not observed')
            time.sleep(.02)

    def close(self):
        for handle in self.handles.values():self.os.k.CloseHandle(handle)
        self.handles.clear()
