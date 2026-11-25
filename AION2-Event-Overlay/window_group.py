"""Keep native overlay surfaces in one owned-window group and coordinate space.

The backdrop owns the HUD, which owns dialogs. Windows keeps owned windows above
their owner, so the backdrop stays below text while the Shell moves the group.
Tk parent relationships are unchanged. Never walk GetParent across ownership.
"""
import ctypes
import os
import tkinter as tk

def system_dpi_awareness():
    # Tk 8.6 does not rescale all controls reliably for per-monitor v2. System
    # awareness deliberately uses one logical space; Windows scales the entire
    # group on mixed-DPI monitors. This avoids mixed physical/Tk hit coordinates.
    if os.name=='nt':
        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError,OSError): ctypes.windll.user32.SetProcessDPIAware()

def hwnd(widget):
    if os.name!='nt': return int(widget.winfo_id())
    u=ctypes.windll.user32
    u.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint]
    u.GetAncestor.restype=ctypes.c_void_p
    return int(u.GetAncestor(ctypes.c_void_p(widget.winfo_id()),2) or widget.winfo_id())

def set_owner(widget,owner):
    if os.name!='nt': return
    u=ctypes.windll.user32
    f=u.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else u.SetWindowLongW
    f.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_ssize_t]; f.restype=ctypes.c_ssize_t
    g=u.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else u.GetWindowLongW
    g.argtypes=f.argtypes[:2]; g.restype=ctypes.c_ssize_t
    target=hwnd(owner) if owner is not None else 0
    if g(hwnd(widget),-8)!=target: f(hwnd(widget),-8,target)

def dialogs(root):
    stack=list(root.winfo_children())
    while stack:
        w=stack.pop()
        if isinstance(w,tk.Toplevel): yield w
        stack.extend(w.winfo_children())

class WindowGroup:
    def __init__(self,app):
        self.app=app; self.root=app.root; self.last=None; self.busy=False
        self.root.bind('<Configure>',self.changed,add='+')
        self.root.bind('<Map>',self.changed,add='+')
        self.root.after_idle(self.sync)

    def changed(self,event):
        if event.widget is self.root and not self.busy:
            rect=(event.x,event.y,event.width,event.height) if event.type==tk.EventType.Configure else None
            if rect is not None and rect==getattr(self,'event_rect',None): return
            self.event_rect=rect
            self.root.after_idle(self.sync)

    def register(self,win,parent=None):
        parent=parent or self.root
        win.transient(parent)
        win._group_parent=parent
        win._group_offset=None
        def moved(event):
            if event.widget is win and not self.busy and win.winfo_ismapped():
                win._group_offset=(win.winfo_x()-parent.winfo_x(),win.winfo_y()-parent.winfo_y())
        win.bind('<Configure>',moved,add='+')
        win.bind('<Map>',lambda e:self.root.after_idle(self.sync),add='+')

    def sync(self):
        if self.busy or not self.root.winfo_exists(): return
        self.busy=True
        try:
            backdrop=getattr(self.app,'drag_surface',None)
            if backdrop is not None and backdrop.winfo_exists():
                set_owner(backdrop,None)
                set_owner(self.root,backdrop)
            current=(self.root.winfo_x(),self.root.winfo_y())
            moved=self.last is not None and current!=self.last
            for win in dialogs(self.root):
                if win is backdrop: continue
                parent=getattr(win,'_group_parent',win.master)
                if not isinstance(parent,(tk.Tk,tk.Toplevel)): parent=self.root
                set_owner(win,parent)
                if not win.winfo_ismapped(): continue
                offset=getattr(win,'_group_offset',None)
                parent_position=(parent.winfo_x(),parent.winfo_y())
                parent_moved=parent_position!=getattr(win,'_group_parent_position',parent_position)
                if offset is None:
                    win._group_offset=(win.winfo_x()-parent.winfo_x(),win.winfo_y()-parent.winfo_y())
                elif moved or parent_moved:
                    x,y=parent.winfo_x()+offset[0],parent.winfo_y()+offset[1]
                    win.geometry(f'+{x}+{y}')
                win._group_parent_position=parent_position
            self.last=current
            self.app.refresh_hud_control_rects()
        except tk.TclError: pass
        finally: self.busy=False

    def display_changed(self):
        # Called after the native procedure has handled the display/settings
        # message. Wrapper handles may have changed; rebuild ownership and rects.
        self.sync(); self.app.sync_drag_surface()
