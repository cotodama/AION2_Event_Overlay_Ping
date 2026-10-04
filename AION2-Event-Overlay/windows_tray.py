"""Windows notification icon. Native callbacks only set flags, never call Tk."""
import ctypes
from ctypes import wintypes as w

PROC=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
class WindowClass(ctypes.Structure):
    _fields_=[('style',w.UINT),('proc',PROC),('clsExtra',ctypes.c_int),('wndExtra',ctypes.c_int),
              ('instance',w.HINSTANCE),('icon',w.HICON),('cursor',w.HANDLE),('brush',w.HANDLE),
              ('menu',w.LPCWSTR),('name',w.LPCWSTR)]
class IconData(ctypes.Structure):
    _fields_=[('size',w.DWORD),('hwnd',w.HWND),('id',w.UINT),('flags',w.UINT),
              ('message',w.UINT),('icon',w.HICON),('tip',w.WCHAR*128),('state',w.DWORD),
              ('stateMask',w.DWORD),('info',w.WCHAR*256),('version',w.UINT),
              ('title',w.WCHAR*64),('infoFlags',w.DWORD),('guid',ctypes.c_byte*16),('balloon',w.HICON)]

class TrayIcon:
    MESSAGE=0x8051
    def __init__(self,icon_path):
        self.restore_requested=False; self.visible=False
        self.user=ctypes.windll.user32; self.shell=ctypes.windll.shell32
        self.user.DefWindowProcW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
        self.user.DefWindowProcW.restype=ctypes.c_ssize_t
        self.user.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,
            ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,w.HMENU,w.HINSTANCE,ctypes.c_void_p]
        self.user.CreateWindowExW.restype=w.HWND
        self.user.LoadImageW.argtypes=[w.HINSTANCE,w.LPCWSTR,w.UINT,ctypes.c_int,ctypes.c_int,w.UINT]
        self.user.LoadImageW.restype=w.HANDLE
        self.shell.Shell_NotifyIconW.argtypes=[w.DWORD,ctypes.POINTER(IconData)]
        self.shell.Shell_NotifyIconW.restype=w.BOOL
        kernel=ctypes.windll.kernel32; kernel.GetModuleHandleW.restype=w.HINSTANCE
        self.instance=kernel.GetModuleHandleW(None)
        self.class_name=f'AION2PingTray_{id(self)}'
        @PROC
        def callback(hwnd,msg,wp,lp):
            if msg==self.MESSAGE:
                if lp & 0xffff in (0x202,0x203,0x205): self.restore_requested=True
                return 0
            return self.user.DefWindowProcW(hwnd,msg,wp,lp)
        self.callback=callback
        wc=WindowClass(); wc.proc=callback; wc.instance=self.instance; wc.name=self.class_name
        if not self.user.RegisterClassW(ctypes.byref(wc)): raise OSError('通知アイコン用ウィンドウの登録失敗')
        self.hwnd=self.user.CreateWindowExW(0,self.class_name,'',0,0,0,0,0,None,None,self.instance,None)
        if not self.hwnd: raise OSError('通知アイコン用ウィンドウの作成失敗')
        self.icon=self.user.LoadImageW(None,str(icon_path),1,32,32,0x10)
        self.data=IconData(); self.data.size=ctypes.sizeof(IconData)
        self.data.hwnd=self.hwnd; self.data.id=1; self.data.flags=1|2|4
        self.data.message=self.MESSAGE; self.data.icon=self.icon; self.data.tip='AION2 Event Overlay + Ping · クリックで復元'

    def show(self):
        self.visible=bool(self.shell.Shell_NotifyIconW(1 if self.visible else 0,ctypes.byref(self.data)))
        return self.visible

    def hide(self):
        if self.visible: self.shell.Shell_NotifyIconW(2,ctypes.byref(self.data))
        self.visible=False

    def close(self):
        self.hide()
        self.user.DestroyWindow.argtypes=[w.HWND]; self.user.DestroyWindow(self.hwnd)
        self.user.DestroyIcon.argtypes=[w.HICON]
        if self.icon: self.user.DestroyIcon(self.icon)
        self.user.UnregisterClassW.argtypes=[w.LPCWSTR,w.HINSTANCE]
        self.user.UnregisterClassW(self.class_name,self.instance)
