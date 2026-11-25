"""Core Audio metadata/diagnostics restricted to sessions owned by this PID."""
import ctypes as c
from ctypes import wintypes as w
import uuid

class GUID(c.Structure):
    _fields_=[('a',w.DWORD),('b',w.WORD),('d',w.WORD),('tail',c.c_ubyte*8)]
    def __init__(self,value):super().__init__();c.memmove(c.byref(self),uuid.UUID(value).bytes_le,16)

def call(ptr,index,*args,types=(),result=c.c_long):
    table=c.cast(ptr,c.POINTER(c.POINTER(c.c_void_p))).contents
    function=c.WINFUNCTYPE(result,c.c_void_p,*types)(table[index])
    value=function(ptr,*args)
    if result is c.c_long and value<0:raise OSError(f'Core Audio HRESULT 0x{value&0xffffffff:08X}')
    return value

def release(ptr):
    if ptr:call(ptr,2,result=w.ULONG)

def query(ptr,iid):
    out=c.c_void_p();guid=GUID(iid)
    call(ptr,0,c.byref(guid),c.byref(out),types=(c.POINTER(GUID),c.POINTER(c.c_void_p)))
    return out

def text_property(ptr,index):
    value=c.c_void_p();call(ptr,index,c.byref(value),types=(c.POINTER(c.c_void_p),))
    try:return c.wstring_at(value) if value else ''
    finally:
        if value:c.windll.ole32.CoTaskMemFree(value)

