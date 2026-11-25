"""Persistent process-owned WASAPI rendering, metadata and mixer controls."""
import ctypes as c
from ctypes import wintypes as w
import os
from windows_audio_session import GUID,call,query,release,text_property

class WaveFormat(c.Structure):
    _pack_=2
    _fields_=[('tag',w.WORD),('channels',w.WORD),('rate',w.DWORD),('bytes_per_second',w.DWORD),
              ('block_align',w.WORD),('bits',w.WORD),('extra',w.WORD)]

class WasapiOutput:
    def __init__(self,name,icon,renderer):
        self.ole=c.WinDLL('ole32');self.renderer=renderer;self.handles=[];self.initialized=False
        self.backend='WASAPI';self.client=self.render=self.control=self.simple=None
        try:
            self.ole.CoInitializeEx.argtypes=[c.c_void_p,w.DWORD]
            hr=self.ole.CoInitializeEx(None,2);self.initialized=hr>=0
            if hr<0 and (hr&0xffffffff)!=0x80010106:raise OSError('Audio COM initialization failed')
            enumerator=c.c_void_p();cls=GUID('BCDE0395-E52F-467C-8E3D-C4579291692E');iid=GUID('A95664D2-9614-4F35-A746-DE8DB63617E6')
            self.ole.CoCreateInstance.argtypes=[c.POINTER(GUID),c.c_void_p,w.DWORD,c.POINTER(GUID),c.POINTER(c.c_void_p)]
            hr=self.ole.CoCreateInstance(c.byref(cls),None,23,c.byref(iid),c.byref(enumerator))
            if hr<0:raise OSError(f'Audio device enumeration 0x{hr&0xffffffff:08X}')
            self.handles.append(enumerator)
            self.enumerator=enumerator
            device=c.c_void_p();call(enumerator,4,0,0,c.byref(device),types=(c.c_int,c.c_int,c.POINTER(c.c_void_p)));self.handles.append(device)
            self.endpoint_id=text_property(device,5)
            self.client=c.c_void_p();iid=GUID('1CB9AD4C-DBFA-4C32-B178-C2F568A703B2')
            call(device,3,c.byref(iid),23,None,c.byref(self.client),types=(c.POINTER(GUID),w.DWORD,c.c_void_p,c.POINTER(c.c_void_p)));self.handles.append(self.client)
            fmt=WaveFormat(3,2,48000,48000*8,8,32,0)
            # A stable, process-specific rendering session with persisted mixer volume.
            session=GUID('376B1990-8107-4AA4-BE38-0701098C37BA')
            call(self.client,3,0,0x88000000,1000000,0,c.byref(fmt),c.byref(session),
                types=(c.c_int,w.DWORD,c.c_longlong,c.c_longlong,c.POINTER(WaveFormat),c.POINTER(GUID)))
            size=w.UINT();call(self.client,4,c.byref(size),types=(c.POINTER(w.UINT),));self.buffer_frames=size.value
            self.render=self.service('F294ACFC-3146-4483-A7BF-ADDCA7C260E2')
            self.control=self.service('F4B1A599-7266-4319-A8CA-E70ACB11E8CD')
            self.control2=query(self.control,'BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D');self.handles.append(self.control2)
            self.simple=self.service('87CE5498-68D6-44E5-9215-6DA47EF883D8')
            call(self.control,5,name,None,types=(w.LPCWSTR,c.c_void_p))
            if icon:call(self.control,7,str(icon),None,types=(w.LPCWSTR,c.c_void_p))
            self.pump();call(self.client,10)
        except Exception:self.close();raise

    def service(self,text):
        ptr=c.c_void_p();iid=GUID(text)
        call(self.client,14,c.byref(iid),c.byref(ptr),types=(c.POINTER(GUID),c.POINTER(c.c_void_p)))
        self.handles.append(ptr);return ptr

    def pump(self):
        padding=w.UINT();call(self.client,6,c.byref(padding),types=(c.POINTER(w.UINT),))
        frames=self.buffer_frames-padding.value
        if not frames:return
        pointer=c.c_void_p();call(self.render,3,frames,c.byref(pointer),types=(w.UINT,c.POINTER(c.c_void_p)))
        flags=2
        try:
            data=self.renderer(frames)
            if not isinstance(data,bytes):
                assert len(data)*data.itemsize==frames*8
                c.memmove(pointer,data.buffer_info()[0],frames*8);flags=0
        finally:call(self.render,4,frames,flags,types=(w.UINT,w.DWORD))

    def status(self,volume=None,mute=None):
        if volume is not None:call(self.simple,3,float(volume),None,types=(c.c_float,c.c_void_p))
        if mute is not None:call(self.simple,5,bool(mute),None,types=(w.BOOL,c.c_void_p))
        scalar=c.c_float();muted=w.BOOL();state=c.c_int();pid=w.DWORD()
        call(self.simple,4,c.byref(scalar),types=(c.POINTER(c.c_float),))
        call(self.simple,6,c.byref(muted),types=(c.POINTER(w.BOOL),))
        call(self.control,3,c.byref(state),types=(c.POINTER(c.c_int),))
        call(self.control2,14,c.byref(pid),types=(c.POINTER(w.DWORD),))
        assert pid.value==os.getpid()
        return dict(pid=pid.value,name=text_property(self.control,4),volume=round(scalar.value,6),muted=bool(muted.value),
            state=state.value,session_id=text_property(self.control2,12))

    def default_changed(self):
        current=c.c_void_p()
        call(self.enumerator,4,0,0,c.byref(current),types=(c.c_int,c.c_int,c.POINTER(c.c_void_p)))
        try:return text_property(current,5)!=self.endpoint_id
        finally:release(current)

    def close(self):
        if self.client:
            try:call(self.client,11)
            except OSError:pass
        for ptr in reversed(self.handles):release(ptr)
        self.handles=[];self.client=None
        if self.initialized:self.ole.CoUninitialize();self.initialized=False
