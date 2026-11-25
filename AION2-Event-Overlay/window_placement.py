"""Absolute coordinates in the current monitor work area, including negative origins."""
import ctypes
import os
import re
from ctypes import wintypes

class MonitorInfo(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]

def work_area(x,y):
    if os.name!='nt': return (0,0,1920,1080)
    u=ctypes.windll.user32
    u.MonitorFromPoint.argtypes=[wintypes.POINT,wintypes.DWORD]; u.MonitorFromPoint.restype=ctypes.c_void_p
    u.GetMonitorInfoW.argtypes=[ctypes.c_void_p,ctypes.POINTER(MonitorInfo)]
    info=MonitorInfo(); info.size=ctypes.sizeof(info)
    if not u.GetMonitorInfoW(u.MonitorFromPoint(wintypes.POINT(int(x),int(y)),2),ctypes.byref(info)):
        raise OSError('Monitor work area unavailable')
    r=info.work; return (r.left,r.top,r.right,r.bottom)

def clamp_window(win,x=None,y=None,width=None,height=None):
    win.update_idletasks()
    # A withdrawn Tk window retains stale winfo dimensions until Map. Its wm
    # geometry already contains the requested size/position we must preserve.
    geometry=re.fullmatch(r'(\d+)x(\d+)([+-]-?\d+)([+-]-?\d+)',win.geometry())
    requested_width,requested_height=width,height
    width,height=win.winfo_width(),win.winfo_height()
    current_x,current_y=win.winfo_x(),win.winfo_y()
    if geometry:
        width,height=map(int,geometry.group(1,2))
        current_x,current_y=(int(n.lstrip('+')) for n in geometry.group(3,4))
    width=requested_width or width; height=requested_height or height
    x=current_x if x is None else int(x); y=current_y if y is None else int(y)
    left,top,right,bottom=work_area(x,y)
    # Space for the native dialog frame/title as well as an 8px edge margin.
    dialog=win is not win._root()
    inset_x=12 if dialog else 8; inset_y=38 if dialog else 8
    width=min(width,right-left-2*inset_x)
    height=min(height,bottom-top-inset_y-12)
    x=max(left+inset_x,min(x,right-width-inset_x))
    y=max(top+inset_y,min(y,bottom-height-12))
    win.geometry(f'{width}x{height}+{x}+{y}')
    return (x,y,width,height)

def restore_taskbar(win):
    if os.name!='nt': return
    from window_group import hwnd
    u=ctypes.windll.user32
    get=u.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else u.GetWindowLongW
    put=u.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else u.SetWindowLongW
    get.argtypes=[ctypes.c_void_p,ctypes.c_int]; get.restype=ctypes.c_ssize_t
    put.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_ssize_t]; put.restype=ctypes.c_ssize_t
    handle=hwnd(win); previous=get(handle,-20); desired=(previous&~0x80)|0x40000
    if previous!=desired:
        put(handle,-20,desired)
        u.SetWindowPos(ctypes.c_void_p(handle),None,0,0,0,0,0x37)
