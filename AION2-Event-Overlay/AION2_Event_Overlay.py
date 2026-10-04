import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import re
try:
    import winsound
except ImportError:
    winsound=None
import json, time, datetime, os, sys, calendar, ctypes, math, struct, wave, tempfile

# cotodama: Ping/status/balance extension; original scheduling and event UI retained.
from ping_feature import PingFeatureMixin
from pathlib import Path

# Tcl needs extended paths for frozen builds under redirected Windows folders.
if getattr(sys, "frozen", False):
    for variable, folder in (("TCL_LIBRARY", "_tcl_data"), ("TK_LIBRARY", "_tk_data")):
        library_path = (Path(sys._MEIPASS) / folder).as_posix()
        if sys.platform == "win32":
            library_path = "//?/UNC/" + library_path[2:] if library_path.startswith("//") else "//?/" + library_path
        os.environ[variable] = library_path

APP_VERSION = "1.1.0-ping"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

def resource_path(name):
    """Return a bundled resource path for source and PyInstaller one-file builds."""
    base=getattr(sys,"_MEIPASS",APP_DIR)
    return os.path.join(base,name)

# Portable settings are separate from the original installed overlay.
PORTABLE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(APP_DIR)
USER_DATA_DIR = os.environ.get("AION2_OVERLAY_DATA_DIR", os.path.join(PORTABLE_DIR, "data"))
CONFIG = os.path.join(USER_DATA_DIR, "aion2_overlay.json")
BUNDLED_CONFIG = resource_path("aion2_overlay.json")
APP_ICON = resource_path("AION2_Event_Overlay.ico")
MAIN_HUD_WIDTH = 390
POSITION_DIR = USER_DATA_DIR
POSITION_FILE = os.path.join(POSITION_DIR, "window_position.json")

DEFAULT_CONFIG = {
    "language": "ja",
    "display_timezone": "JST",
    "background_opacity": 0.88,
    "alert_volume": 45,
    "alert_sound_file": "",
    "timer_alert_volume": 45,
    "timer_alert_sound_file": "",
    "events": [
        {"name_ja":"時空の亀裂","name_en":"Spacetime Rift","type":"interval","start":"02:00","interval_minutes":180,"duration_minutes":60,"entry_minutes":10,"notify_before_minutes":5,"alert_timing":"start_only","enabled":True},
        {"name_ja":"シューゴフェスタ","name_en":"Shugo Festa","type":"interval","start":"00:00","interval_minutes":60,"duration_minutes":10,"entry_minutes":5,"notify_before_minutes":5,"alert_timing":"start_only","enabled":True},
        {"name_ja":"戦場","name_en":"Battlefield","type":"windows","windows":[["11:00","14:00"],["19:00","21:00"]],"notify_before_minutes":5,"alert_timing":"start_only","enabled":True},
        {"name_ja":"アーティファクト占領戦","name_en":"Artifact Siege","type":"weekly","weekdays":[2,5],"times":["21:00"],"duration_minutes":30,"entry_minutes":0,"notify_before_minutes":30,"alert_timing":"start_only","enabled":True}
    ],
    "timers": [
        {"name":"タイマー1","duration":300,"visible":False},
        {"name":"タイマー2","duration":600,"visible":False},
        {"name":"タイマー3","duration":900,"visible":False}
    ]
}

def deep_default():
    return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))

def load_config():
    if not os.path.exists(CONFIG):
        initial=deep_default()
        try:
            if os.path.exists(BUNDLED_CONFIG):
                with open(BUNDLED_CONFIG,"r",encoding="utf-8") as f:
                    bundled=json.load(f)
                if isinstance(bundled,dict):
                    initial.update(bundled)
        except Exception as e:
            print(f"[AION2 Overlay] Bundled config read failed; using defaults: {e}")
        save_config(initial)
        return initial
    try:
        with open(CONFIG,"r",encoding="utf-8") as f:
            c=json.load(f)
        for k,v in DEFAULT_CONFIG.items():
            c.setdefault(k,json.loads(json.dumps(v)))

        # Pre-public default migration. Preserve explicit custom values, but update
        # untouched Shugo Festa / Battlefield alert defaults from earlier builds.
        for e in c.get("events",[]):
            name_en=e.get("name_en","")
            if name_en=="Shugo Festa":
                if int(e.get("notify_before_minutes",0) or 0)==0:
                    e["notify_before_minutes"]=5
                if e.get("alert_timing","both")=="both":
                    e["alert_timing"]="start_only"
            elif name_en=="Battlefield":
                if "notify_before_minutes" not in e:
                    e["notify_before_minutes"]=5
                if "alert_timing" not in e:
                    e["alert_timing"]="start_only"
        return c
    except Exception as e:
        print(f"[AION2 Overlay] User config read failed; using defaults: {e}")
        return deep_default()

def save_config(c):
    os.makedirs(USER_DATA_DIR,exist_ok=True)
    tmp=CONFIG+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:
        json.dump(c,f,ensure_ascii=False,indent=2)
    os.replace(tmp,CONFIG)

def fmt(sec):
    sec=max(0,int(sec)); h,r=divmod(sec,3600); m,s=divmod(r,60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def parse_hm(s):
    h,m=map(int,s.strip().split(":"))
    if not (0<=h<=23 and 0<=m<=59): raise ValueError
    return h*3600+m*60

def nth_weekday(year, month, weekday, n):
    c=calendar.Calendar().monthdayscalendar(year,month)
    days=[w[weekday] for w in c if w[weekday]]
    return days[n-1]

def last_weekday(year,month,weekday):
    c=calendar.Calendar().monthdayscalendar(year,month)
    days=[w[weekday] for w in c if w[weekday]]
    return days[-1]

# Dependency-free timezone conversion for the three requested display zones.
# PDT/PST: US DST = 2nd Sunday Mar 02:00 local to 1st Sunday Nov 02:00 local.
# CEST/CET: EU DST = last Sunday Mar 01:00 UTC to last Sunday Oct 01:00 UTC.
def us_pacific_offset(utc_dt):
    y=utc_dt.year
    mar=nth_weekday(y,3,6,2)
    nov=nth_weekday(y,11,6,1)
    start=datetime.datetime(y,3,mar,10,0,0,tzinfo=datetime.timezone.utc) # 02:00 PST
    end=datetime.datetime(y,11,nov,9,0,0,tzinfo=datetime.timezone.utc)   # 02:00 PDT
    return (-7,"PDT") if start<=utc_dt<end else (-8,"PST")

def europe_central_offset(utc_dt):
    y=utc_dt.year
    mar=last_weekday(y,3,6); octo=last_weekday(y,10,6)
    start=datetime.datetime(y,3,mar,1,0,0,tzinfo=datetime.timezone.utc)
    end=datetime.datetime(y,10,octo,1,0,0,tzinfo=datetime.timezone.utc)
    return (2,"CEST") if start<=utc_dt<end else (1,"CET")

def display_time(utc_dt, zone):
    if zone=="PDT":
        off,label=us_pacific_offset(utc_dt)
    elif zone=="CEST":
        off,label=europe_central_offset(utc_dt)
    else:
        off,label=9,"JST"
    return utc_dt+datetime.timedelta(hours=off),label


class TimerState:
    def __init__(self,d):
        self.name=d.get("name","Timer"); self.duration=max(1,int(d.get("duration",300)))
        self.visible=bool(d.get("visible",True)); self.alert_enabled=bool(d.get("alert_enabled",True))
        self.running=False; self.elapsed=0.0; self.started=None; self.alert_fired=False
    def start(self):
        if not self.running:
            if self.elapsed >= self.duration:
                self.elapsed=0.0
            self.started=time.monotonic()-self.elapsed; self.running=True
            if self.elapsed < self.duration:
                self.alert_fired=False
    def stop(self):
        if self.running: self.elapsed=time.monotonic()-self.started; self.running=False
    def reset(self): self.running=False; self.elapsed=0; self.started=None; self.alert_fired=False
    def vals(self):
        e=time.monotonic()-self.started if self.running else self.elapsed
        return max(0,self.duration-e), max(0,e-self.duration), e

# --- Windows native compositor backdrop (v4.16) ---
# Uses one HWND only. Unlike the old auxiliary Toplevel approach, the backdrop
# cannot move in front of the text/input surface when AION2 receives focus.
if os.name=="nt":
    class _ACCENTPOLICY(ctypes.Structure):
        _fields_=[
            ("AccentState",ctypes.c_int),
            ("AccentFlags",ctypes.c_int),
            ("GradientColor",ctypes.c_uint),
            ("AnimationId",ctypes.c_int),
        ]
    class _WINCOMPATTRDATA(ctypes.Structure):
        _fields_=[
            ("Attribute",ctypes.c_int),
            ("Data",ctypes.c_void_p),
            ("SizeOfData",ctypes.c_size_t),
        ]


HUD_TRANSPARENT_KEY="#010203"

if os.name=="nt":
    WM_NCHITTEST=0x0084
    HTTRANSPARENT=-1
    HTCLIENT=1
    GWL_WNDPROC=-4
    GWL_EXSTYLE=-20
    WS_EX_TRANSPARENT=0x00000020
    WS_EX_LAYERED=0x00080000
    _WNDPROC_TYPE=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t)


class App(PingFeatureMixin):
    def __init__(self,root):
        self._dialog_windows = {}
        self.root=root; self.cfg=load_config()
        self.init_ping(USER_DATA_DIR)
        self.timers=[TimerState(x) for x in self.cfg["timers"]]
        self.event_alert_state={}
        self.alert_wav=os.path.join(tempfile.gettempdir(),"aion2_event_overlay_alert.wav")
        root.title("AION2 Event Overlay + Ping")
        try:
            root.iconbitmap(APP_ICON)
        except Exception as e:
            print(f"[AION2 Overlay] Window icon load failed: {e}")
        root.geometry("+30+40"); root.minsize(290,1)
        root.configure(bg="#101215"); root.attributes("-topmost",True)
        self.bg_alpha=float(self.cfg.get("background_opacity",.88)); self.bg_alpha=self.bg_alpha/100.0 if self.bg_alpha>1.0 else self.bg_alpha
        self.cfg["background_opacity"]=(100-self.ping_cfg['transparency'])/100
        self.bg_alpha=self.cfg["background_opacity"]
        root.attributes("-topmost",self.ping_cfg['topmost'])
        self.setup_fonts()
        self.build()
        self.install_surface_drag()
        self.apply_main_hud_surface_style()
        self.apply_background_opacity()
        # Frameless/native styling can recreate the Windows wrapper HWND.
        # Restore only after that startup work has settled, then enable autosave.
        self._position_restore_in_progress=True
        self.root.after(220,self.restore_window_position)
        print(f"[AION2 Overlay] Version {APP_VERSION}; user data={USER_DATA_DIR}")
        self.root.after(420,self._finish_position_restore)
        root.bind("<Configure>",self.schedule_window_position_save,add="+")
        root.protocol("WM_DELETE_WINDOW",self.on_close)
        self.tick()
        self.root.after(250,self.print_native_hwnd_diagnostics)

    def setup_fonts(self):
        """Choose Noto Sans JP for UI text and Consolas for clocks/countdowns."""
        try:
            families=set(tkfont.families(self.root))
        except Exception:
            families=set()
        self.ui_font="Noto Sans JP" if "Noto Sans JP" in families else "Yu Gothic UI"
        self.mono_font="Consolas" if "Consolas" in families else "Courier New"

    def ui(self,size=9,weight="normal"):
        return (self.ui_font,size,weight)

    def small_ui(self,size=9,weight="normal"):
        return ("Meiryo UI",size,weight)

    def mono(self,size=10,weight="normal"):
        return (self.mono_font,size,weight)

    def tr(self,ja,en): return en if self.cfg.get("language")=="en" else ja


    def panel_colors(self):
        return {
            "root":"#202020",
            "header":"#202020",
            "card":"#202020",
            "button":"#202934",
            "timerbutton":"#202934",
        }




    def _native_backdrop_color(self, alpha):
        """Return ABGR gradient color used by Windows AccentPolicy."""
        # Windows-dark neutral tint: #202020. Alpha controls backdrop strength.
        a=max(0,min(255,int(alpha*255)))
        r=g=b=0x20
        return (a<<24)|(b<<16)|(g<<8)|r

    def apply_native_backdrop(self):
        """Single-HWND alpha-tint experiment (no auxiliary Toplevel).

        Windows draws the translucent dark surface in the SAME native HWND as Tk.
        Tk foreground glyphs/icons stay opaque; only transparent-key structural
        areas reveal the compositor tint.
        """
        if os.name!="nt":
            return False
        try:
            self.root.update_idletasks()
            hwnd=self.get_native_toplevel_hwnd()
            opacity=float(self.cfg.get("background_opacity",0.70))
            if opacity>1.0: opacity/=100.0
            opacity=max(0.0,min(1.0,opacity))

            self.root.attributes("-alpha",1.0)
            try:self.root.wm_attributes("-transparentcolor",HUD_TRANSPARENT_KEY)
            except Exception:pass

            policy=_ACCENTPOLICY()
            # Disable Accent tint: some Windows/GPU combinations render it white.
            # The explicitly dark backing surface provides background-only alpha.
            policy.AccentState=0
            policy.AccentFlags=0
            policy.GradientColor=self._native_backdrop_color(opacity)
            policy.AnimationId=0

            data=_WINCOMPATTRDATA()
            data.Attribute=19
            data.Data=ctypes.cast(ctypes.pointer(policy),ctypes.c_void_p)
            data.SizeOfData=ctypes.sizeof(policy)

            fn=ctypes.windll.user32.SetWindowCompositionAttribute
            ok=bool(fn(hwnd,ctypes.byref(data)))
            print(f"[AION2 Overlay] Dark overlay background opacity={opacity:.2f}, native={ok}")
            return ok
        except Exception as exc:
            print(f"[AION2 Overlay] Single-HWND alpha tint failed: {exc}")
            return False

    def _new_dialog(self, title):
        """Build dialogs hidden; reveal only after their first page is complete."""
        win=tk.Toplevel(self.root)
        win.withdraw()
        win.title(title)
        self.setup_dialog_position(win,title)
        return win

    def _safe_dialog_close(self, win):
        try: win.grab_release()
        except Exception: pass
        try: win.destroy()
        except Exception: pass

    def _place_compact_dialog(self, win, width=390, min_height=260):
        try:
            win.update_idletasks()
            sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
            h=max(min_height,min(win.winfo_reqheight()+8,sh-90))
            rx,ry=self.root.winfo_x(),self.root.winfo_y()
            rw=self.root.winfo_width()
            if win.winfo_ismapped():
                x,y=win.winfo_x(),win.winfo_y()
            elif win._position_key in self.dialog_positions:
                pos=self.dialog_positions[win._position_key]; x,y=pos['x'],pos['y']
            else:
                x=rx+rw+12; y=ry
            win.geometry(f"{width}x{h}+{x}+{y}")
        except Exception:
            pass

    def preview_background_opacity(self, value):
        """Preview native background opacity without saving settings."""
        try:
            old=self.cfg.get("background_opacity",70)
            self.cfg["background_opacity"]=float(value)
            self.apply_background_opacity()
            self.cfg["background_opacity"]=old
        except Exception:
            pass



    def apply_background_opacity(self):
        """Keep foreground opaque and render opacity on the dark backing surface."""
        opacity=float(self.cfg.get("background_opacity",0.70))
        if opacity>1.0: opacity/=100.0
        opacity=max(0.0,min(1.0,opacity))
        self.ping_cfg['transparency']=round((1-opacity)*100)
        try:
            self.root.attributes("-alpha",1.0)
            self.root.attributes("-topmost",self.ping_cfg['topmost'])
        except Exception:
            pass
        self.apply_native_backdrop()
        if hasattr(self,'drag_surface'): self.sync_drag_surface()


    def _interactive_widget_at_screen(self, sx, sy):
        """Only explicit HUD controls consume clicks.

        Labels, text, frames, cards, canvas backgrounds and empty HUD space are
        intentionally click-through. This avoids Tk class/binding inheritance
        accidentally making whole card/header regions interactive.
        """
        try:
            w=self.root.winfo_containing(int(sx),int(sy))
        except Exception:
            return False
        if w is None:
            return False

        # Explicit native Tk controls.
        interactive_classes={
            "Button","TButton","Checkbutton","TCheckbutton","Scale","TScale",
            "Entry","TEntry","Spinbox","TSpinbox","Combobox","TCombobox",
            "Listbox","Scrollbar","TScrollbar"
        }

        cur=w
        while cur is not None:
            try:
                cls=cur.winfo_class()
            except Exception:
                cls=""
            if cls in interactive_classes:
                return True

            # Do NOT use generic <Button-1> binding detection here.
            # Tk bindings can be inherited/class-level and caused labels,
            # card canvases and header areas to block click-through in v4.18.0.
            if cur is self.root:
                break
            try:
                cur=cur.master
            except Exception:
                break

        # Canvas-based HUD controls (bell / icon hit areas) are handled by
        # explicit screen rectangles registered below.
        for rect in getattr(self,"_hud_control_rects",()):
            try:
                x1,y1,x2,y2=rect
                if x1 <= sx < x2 and y1 <= sy < y2:
                    return True
            except Exception:
                pass
        return False

    def refresh_hud_control_rects(self):
        """Register only visible HUD widgets that are meant to be clickable."""
        rects=[]
        # Existing explicit Button widgets are already detected by class.
        # For canvas/label controls, register widgets that the app marks here.
        for name in ("btn_timer","btn_settings"):
            w=getattr(self,name,None)
            if w is None:
                continue
            try:
                if w.winfo_ismapped():
                    x=w.winfo_rootx(); y=w.winfo_rooty(); pad=8
                    rects.append((x-pad,y-pad,x+w.winfo_width()+pad,y+w.winfo_height()+pad))
            except Exception:
                pass

        # Timer + is always an interactive control, even in frameless mode.
        w=getattr(self,"timer_add_btn",None)
        if w is not None:
            try:
                if w.winfo_ismapped():
                    x=w.winfo_rootx(); y=w.winfo_rooty(); pad=10
                    rects.append((x-pad,y-pad,x+w.winfo_width()+pad,y+w.winfo_height()+pad))
            except Exception:
                pass
        # New scroll surfaces and summary rows support scrolling and double-click editing.
        for area in (getattr(self,'list_area',None),getattr(self,'summary_area',None)):
            w=getattr(area,'canvas',None)
            try:
                if w is not None and w.winfo_exists() and w.winfo_ismapped():
                    x=w.winfo_rootx(); y=w.winfo_rooty()
                    rects.append((x,y,x+w.winfo_width(),y+w.winfo_height()))
            except Exception:
                pass
        self._hud_control_rects=rects


    def _enum_child_hwnds(self, parent_hwnd):
        if os.name!="nt":
            return []
        result=[]
        try:
            user32=ctypes.windll.user32
            ENUMPROC=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_ssize_t)
            @ENUMPROC
            def cb(hwnd,lparam):
                result.append(int(hwnd))
                return True
            user32.EnumChildWindows(ctypes.c_void_p(parent_hwnd),cb,0)
        except Exception:
            pass
        return result

    def install_selective_hit_test(self):
        """Subclass root AND Tk child HWNDs.

        Tk labels/frames/canvases can own child HWND hit-test paths, so the hook
        is applied to every HUD HWND rather than only the native root wrapper.
        """
        if os.name!="nt":
            return
        try:
            self.root.update_idletasks()
            user32=ctypes.PyDLL('user32.dll')
            user32.CallWindowProcW.restype=ctypes.c_ssize_t
            user32.CallWindowProcW.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
            get_wlp=getattr(user32,"GetWindowLongPtrW",user32.GetWindowLongW)
            set_wlp=getattr(user32,"SetWindowLongPtrW",user32.SetWindowLongW)

            root_hwnd=int(self.root.winfo_id())
            hwnds=[root_hwnd]+self._enum_child_hwnds(root_hwnd)
            self._subclass_records={}

            for hwnd in hwnds:
                try:
                    old_proc=int(get_wlp(ctypes.c_void_p(hwnd),GWL_WNDPROC))
                    if not old_proc:
                        continue

                    @_WNDPROC_TYPE
                    def _proc(hWnd,msg,wParam,lParam,_old=old_proc):
                        try:
                            if msg==WM_NCHITTEST:
                                self.refresh_hud_control_rects()
                                x=ctypes.c_short(lParam & 0xFFFF).value
                                y=ctypes.c_short((lParam >> 16) & 0xFFFF).value
                                # The overlay surface now accepts drag input everywhere.
                                return HTCLIENT
                        except Exception:
                            pass
                        return user32.CallWindowProcW(
                            ctypes.c_void_p(_old),hWnd,msg,wParam,lParam
                        )

                    set_wlp(ctypes.c_void_p(hwnd),GWL_WNDPROC,
                            ctypes.cast(_proc,ctypes.c_void_p).value)
                    self._subclass_records[hwnd]=(old_proc,_proc)
                except Exception:
                    continue

            self._selective_hit_test_installed=bool(self._subclass_records)
        except Exception:
            self._selective_hit_test_installed=False


    def restore_selective_hit_test(self):
        if os.name!="nt" or not getattr(self,"_selective_hit_test_installed",False):
            return
        try:
            user32=ctypes.windll.user32
            set_wlp=getattr(user32,"SetWindowLongPtrW",user32.SetWindowLongW)
            for hwnd,(old_proc,callback) in list(getattr(self,"_subclass_records",{}).items()):
                try:
                    set_wlp(ctypes.c_void_p(hwnd),GWL_WNDPROC,old_proc)
                except Exception:
                    pass
        except Exception:
            pass
        self._subclass_records={}
        self._selective_hit_test_installed=False


    def print_native_hwnd_diagnostics(self):
        if os.name!="nt":
            return
        try:
            client=int(self.root.winfo_id())
            top=self.get_native_toplevel_hwnd()
            user32=ctypes.windll.user32
            GWL_EXSTYLE_LOCAL=-20
            get_wlp=getattr(user32,"GetWindowLongPtrW",user32.GetWindowLongW)
            ex=int(get_wlp(ctypes.c_void_p(top),GWL_EXSTYLE_LOCAL))
            transparent=bool(ex & 0x20)
            print(f"[AION2 Overlay] Tk client HWND={client:#x}, top-level HWND={top:#x}, EXSTYLE={ex:#x}, frameless=True, clickthrough={transparent}")
        except Exception as exc:
            print(f"[AION2 Overlay] HWND diagnostic failed: {exc}")








    def get_native_toplevel_hwnd(self):
        """Return the real Windows top-level wrapper HWND for the Tk root."""
        if os.name!="nt":
            return int(self.root.winfo_id())
        self.root.update_idletasks()
        user32=ctypes.windll.user32
        hwnd=int(self.root.winfo_id())
        # Tk commonly exposes a child/client HWND through winfo_id().
        # Walk parents until the native top-level wrapper is reached.
        last=hwnd
        seen=set()
        while hwnd and hwnd not in seen:
            seen.add(hwnd)
            parent=int(user32.GetParent(ctypes.c_void_p(hwnd)) or 0)
            if not parent:
                break
            last=parent
            hwnd=parent
        return int(last)


    def set_frameless_clickthrough(self, enabled):
        """Pass through non-controls only; buttons/bells remain clickable."""
        if os.name!="nt":
            return
        try:
            self.root.update_idletasks()
            hwnd=self.get_native_toplevel_hwnd()
            user32=ctypes.windll.user32
            get_wlp=getattr(user32,"GetWindowLongPtrW",user32.GetWindowLongW)
            set_wlp=getattr(user32,"SetWindowLongPtrW",user32.SetWindowLongW)
            ex=int(get_wlp(ctypes.c_void_p(hwnd),GWL_EXSTYLE))
            # Never make the whole HWND transparent to input.
            ex &= ~WS_EX_TRANSPARENT
            ex = (ex & ~0x80) | 0x40000  # taskbar app, not a hidden tool window
            ex |= WS_EX_LAYERED
            set_wlp(ctypes.c_void_p(hwnd),GWL_EXSTYLE,ex)
            if enabled:
                self.restore_selective_hit_test()
                self.install_selective_hit_test()
            else:
                self.restore_selective_hit_test()
            SWP_NOMOVE=0x0002; SWP_NOSIZE=0x0001
            SWP_NOZORDER=0x0004; SWP_NOACTIVATE=0x0010; SWP_FRAMECHANGED=0x0020
            user32.SetWindowPos(ctypes.c_void_p(hwnd),None,0,0,0,0,
                SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_FRAMECHANGED)
        except Exception:
            pass




    def apply_frameless_mode(self):
        """Apply the permanent, stable frameless HUD mode."""
        self.root.overrideredirect(True)
        try:
            self.root.update_idletasks()
            self.set_frameless_clickthrough(True)
            self.root.after(80,lambda:self.set_frameless_clickthrough(True))
            self.root.after(180,self.apply_background_opacity)
            self.root.after(300,self.print_native_hwnd_diagnostics)
        except Exception:
            pass

    def fit_window_to_content(self):
        """Fit height only; keep the overlay deliberately narrow and stable."""
        try:
            if getattr(self,'window_maximized',False): return
            self.root.update_idletasks()
            x=self.root.winfo_x(); y=self.root.winfo_y()
            # The HUD is intentionally portrait/vertical. Never let a child widget
            # silently grow the main window horizontally.
            w=getattr(self,'overlay_width',MAIN_HUD_WIDTH)
            requested=max(1,self.root.winfo_reqheight())
            h=getattr(self,'manual_height',None) or min(requested,self.root.winfo_screenheight()-60)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def build_alert_wav(self, volume_key="alert_volume", output_path=None):
        """Create a short, gentle two-note chime at the configured volume."""
        try:
            rate=44100
            volume=max(0,min(100,int(self.cfg.get(volume_key,45))))/100.0
            # Soft attack/decay and modest peak level so it is noticeable but not intrusive.
            notes=[(659.25,0.16),(783.99,0.24)]
            samples=[]
            for freq,dur in notes:
                count=int(rate*dur)
                for i in range(count):
                    t=i/rate
                    attack=min(1.0,t/0.025)
                    release=min(1.0,max(0.0,(dur-t)/0.10))
                    env=attack*release
                    s=math.sin(2*math.pi*freq*t)
                    samples.append(int(32767*0.20*volume*env*s))
                samples.extend([0]*int(rate*0.045))
            with wave.open(output_path or self.alert_wav,"wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
                wf.writeframes(b"".join(struct.pack("<h",x) for x in samples))
        except Exception:
            pass

    def play_mp3(self,path,volume_key="alert_volume",alias="aion2_alert"):
        """Play an MP3 asynchronously through Windows MCI without extra Python packages."""
        try:
            # Stop/close a previous custom MP3 alias first.
            ctypes.windll.winmm.mciSendStringW(f"stop {alias}",None,0,None)
            ctypes.windll.winmm.mciSendStringW(f"close {alias}",None,0,None)
            safe=path.replace('"','')
            cmd=f'open "{safe}" type mpegvideo alias {alias}'
            if ctypes.windll.winmm.mciSendStringW(cmd,None,0,None)!=0:
                return False
            # MCI volume is 0..1000.
            vol=max(0,min(100,int(self.cfg.get(volume_key,45))))*10
            ctypes.windll.winmm.mciSendStringW(f"setaudio {alias} volume to {vol}",None,0,None)
            return ctypes.windll.winmm.mciSendStringW(f"play {alias}",None,0,None)==0
        except Exception:
            return False

    def play_event_alert(self):
        if winsound is None or int(self.cfg.get("alert_volume",45))<=0:
            return
        try:
            custom=self.cfg.get("alert_sound_file","").strip()
            if custom and os.path.isfile(custom):
                ext=os.path.splitext(custom)[1].lower()
                if ext==".wav":
                    winsound.PlaySound(custom,winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
                    return
                if ext==".mp3" and self.play_mp3(custom):
                    return
            # Default: the built-in gentle two-note chime.
            self.build_alert_wav()
            winsound.PlaySound(self.alert_wav,winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
        except Exception:
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    def play_timer_alert(self):
        """Timer completion alert; independent volume/sound, enabled per timer."""
        if winsound is None or int(self.cfg.get("timer_alert_volume",45))<=0:
            return
        try:
            custom=self.cfg.get("timer_alert_sound_file","").strip()
            if custom and os.path.isfile(custom):
                ext=os.path.splitext(custom)[1].lower()
                if ext==".wav":
                    winsound.PlaySound(custom,winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
                    return
                if ext==".mp3" and self.play_mp3(custom,"timer_alert_volume","aion2_timer_alert"):
                    return
            # Slightly longer but still restrained (~0.7 s) three-note completion chime.
            path=os.path.join(tempfile.gettempdir(),"aion2_timer_overlay_alert.wav")
            rate=44100
            volume=max(0,min(100,int(self.cfg.get("timer_alert_volume",45))))/100.0
            samples=[]
            for freq,dur in ((523.25,.16),(659.25,.16),(783.99,.24)):
                count=int(rate*dur)
                for i in range(count):
                    tt=i/rate
                    env=min(1.0,tt/.025)*min(1.0,max(0.0,(dur-tt)/.09))
                    samples.append(int(32767*.18*volume*env*math.sin(2*math.pi*freq*tt)))
                samples.extend([0]*int(rate*.045))
            with wave.open(path,"wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
                wf.writeframes(b"".join(struct.pack("<h",x) for x in samples))
            winsound.PlaySound(path,winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
        except Exception:
            try: winsound.MessageBeep(winsound.MB_OK)
            except Exception: pass

    def toggle_event_alert(self,e,button=None):
        e["alert_enabled"]=not bool(e.get("alert_enabled",False))
        save_config(self.cfg)
        if button is not None:
            on=e["alert_enabled"]
            button.config(text=("🔔" if on else "🔕"),fg=("#dcecff" if on else "#6f7885"))

    def apply_main_hud_surface_style(self):
        """Make HUD structure transparent while keeping glyphs/icons opaque.

        Background tint/alpha is provided once by the Windows compositor.
        Tk structural widgets use the transparent key so they do not add a second,
        non-adjustable dark rectangle.
        """
        key=HUD_TRANSPARENT_KEY
        try:self.root.configure(bg=key)
        except Exception:pass
        for name in ("header","header_info","header_buttons","event_section","event_box","timer_box","timer_content"):
            w=getattr(self,name,None)
            if w is not None:
                try:w.configure(bg=key)
                except Exception:pass

        # Buttons remain intentionally opaque/interactive. Everything else that is
        # merely structural becomes a compositor hole.
        for parent_name in ("header","event_box","timer_box"):
            parent=getattr(self,parent_name,None)
            if parent is None: continue
            stack=[parent]
            while stack:
                w=stack.pop()
                try: stack.extend(w.winfo_children())
                except Exception: pass
                try:
                    if isinstance(w,(tk.Frame,tk.LabelFrame)):
                        w.configure(bg=key)
                except Exception:
                    pass

        # Canvas surfaces use the same key; Canvas text itself stays fully opaque.
        for w in getattr(self,"event_widgets",[]):
            try:w[1].configure(bg=key)
            except Exception:pass
        try:self.header_canvas.configure(bg=key)
        except Exception:pass


    def rebuild_event_widgets(self):
        c=self.panel_colors()
        # event_box is the event-card container created by build().
        # v4.13.0 incorrectly referenced a non-existent events_body attribute.
        for w in self.event_box.winfo_children():
            w.destroy()
        self.event_widgets=[]
        self.bell_buttons=[]
        for e in self.cfg["events"]:
            if not e.get("enabled",True):
                continue
            card=tk.Canvas(self.event_box,height=66,bg=HUD_TRANSPARENT_KEY,highlightthickness=0,bd=0)
            card.pack(fill="x",padx=5,pady=3)
            # No stipple: transparent Canvas reveals the smooth alpha layer below.
            bg=card.create_rectangle(1,1,1000,65,fill=HUD_TRANSPARENT_KEY,outline="#555555",
                                     width=1,tags=("cardbg",))
            name_item=card.create_text(12,17,text=self.event_name(e),anchor="w",
                                       fill="#f1f5f9",font=self.ui(10,"bold"))
            status_item=card.create_text(12,45,text="",anchor="w",
                                         fill="#dcecff",font=self.small_ui(10,"bold"))
            time_item=card.create_text(84,45,text="",anchor="w",
                                       fill="#bcdcff",font=self.mono(12,"bold"))
            alert_on=bool(e.get("alert_enabled",False))
            bell_item=card.create_text(100,17,text=("🔔" if alert_on else "🔕"),anchor="e",
                                       fill=("#dcecff" if alert_on else "#718096"),
                                       font=self.small_ui(10))

            def resize(ev,cv=card,bg=bg,bell=bell_item):
                cv.coords(bg,1,1,max(2,ev.width-1),65)
            card.bind("<Configure>",resize)

            # Genuine square button: same interaction model as timer/settings/+.
            # It covers a predictable area instead of relying on glyph hit testing.
            bell_holder={}
            def bell_button_toggle(e=e,cv=card,bell=bell_item,holder=bell_holder):
                self.toggle_event_alert(e)
                on=bool(e.get("alert_enabled",False))
                cv.itemconfigure(bell,text="",state="hidden")
                btn=holder.get("button")
                if btn:
                    btn.config(text=("🔔" if on else "🔕"),
                               fg=("#dcecff" if on else "#8b98a6"))
            card.itemconfigure(bell_item,text="",state="hidden")
            bell_btn=self.make_hud_square_button(
                card,("🔔" if alert_on else "🔕"),bell_button_toggle,size=34,
                font=self.small_ui(10))
            bell_holder["button"]=bell_btn
            bell_btn.config(fg=("#dcecff" if alert_on else "#8b98a6"))
            bell_btn.place(relx=1.0,x=-7,y=7,width=34,height=34,anchor="ne")
            if not hasattr(self,"bell_buttons"): self.bell_buttons=[]
            self.bell_buttons.append(bell_btn)

            self.event_widgets.append((e,card,name_item,status_item,time_item))

    def localized_timer_name(self,name):
        """Translate only built-in/default timer names; preserve user-defined names."""
        name=str(name or "")
        lang=self.cfg.get("language","ja")
        if lang=="en":
            if name=="新しいタイマー":
                return "New Timer"
            m=re.fullmatch(r"タイマー-(\d+)",name)
            if m:
                return f"Timer {m.group(1)}"
        else:
            if name=="New Timer":
                return "新しいタイマー"
            m=re.fullmatch(r"Timer\s+(\d+)",name,re.IGNORECASE)
            if m:
                return f"タイマー-{m.group(1)}"
        return name

    def event_name(self,e):
        if self.cfg.get("language")=="en":
            return e.get("name_en") or e.get("name_ja") or "Event"
        return e.get("name_ja") or e.get("name_en") or "イベント"

    def event_status(self,e,jst):
        sod=jst.hour*3600+jst.minute*60+jst.second
        typ=e.get("type","daily")
        if typ=="interval":
            start=parse_hm(e.get("start","00:00"))
            iv=max(60,int(e.get("interval_minutes",60))*60)
            x=(sod-start)%iv
            entry=max(0,int(e.get("entry_minutes",0))*60)
            if entry and x<entry:
                return "entry",entry-x,entry-x
            return "next",iv-x,None
        if typ=="daily":
            target=parse_hm(e.get("start","00:00"))
            entry=max(0,int(e.get("entry_minutes",0))*60)
            if entry and target<=sod<target+entry:
                return "entry",target+entry-sod,target+entry-sod
            return "next",(target-sod)%86400,None
        if typ=="windows":
            wins=e.get("windows",[])
            for a,b in wins:
                aa,bb=parse_hm(a),parse_hm(b)
                if aa<=sod<bb:return "active",0,bb-sod
                if sod<aa:return "next",aa-sod,None
            return ("next",86400-sod+parse_hm(wins[0][0]),None) if wins else ("next",0,None)
        if typ=="weekly":
            cand=[]; wd=jst.weekday()
            for add in range(8):
                d=(wd+add)%7
                if d not in e.get("weekdays",[]):continue
                for hm in e.get("times",[]):
                    target=parse_hm(hm); delta=add*86400+target-sod
                    if delta>=0:cand.append(delta)
            return "next",min(cand) if cand else 7*86400,None
        return "next",0,None

    def rebuild_timers(self):
        for w in self.timer_content.winfo_children():w.destroy()
        self.timer_widgets=[]
        c=self.panel_colors()
        for timer in self.timers:
            if not timer.visible: continue
            f=tk.Frame(self.timer_content,bg=HUD_TRANSPARENT_KEY,
                       highlightthickness=1,highlightbackground="#52606b")
            f.pack(fill="x",padx=5,pady=4)

            top=tk.Frame(f,bg=HUD_TRANSPARENT_KEY)
            top.pack(fill="x",padx=8,pady=(5,2))
            display_timer_name=self.localized_timer_name(timer.name)
            tk.Label(top,text=display_timer_name,font=self.ui(10,"bold"),fg="white",
                     bg=HUD_TRANSPARENT_KEY).pack(side="left",anchor="center")

            def square(parent,text,command,font=None):
                holder=tk.Frame(parent,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
                holder.pack(side="right")
                holder.pack_propagate(False)
                b=self.make_hud_square_button(holder,text,command,size=34,font=font)
                b.place(relx=.5,rely=.5,anchor="center",width=34,height=34)
                return b

            def hide_timer(tmr=timer):
                tmr.visible=False; self.save_timers(); self.rebuild_timers()
                self.root.after_idle(self.fit_window_to_content)

            minus=square(top,"−",hide_timer,self.ui(11,"bold"))

            time_row=tk.Frame(f,bg=HUD_TRANSPARENT_KEY)
            time_row.pack(fill="x",padx=8,pady=(0,2))
            val=tk.Label(time_row,text=fmt(timer.duration),font=self.mono(18,"bold"),
                         fg="white",bg=HUD_TRANSPARENT_KEY)
            val.pack(side="left",anchor="center")
            finish=tk.Label(time_row,text="",font=self.ui(9,"bold"),fg="#f0b3b3",
                            bg=HUD_TRANSPARENT_KEY,anchor="e")
            finish.pack(side="right",anchor="center",padx=(10,0))

            controls=tk.Frame(f,bg=HUD_TRANSPARENT_KEY)
            controls.pack(fill="x",padx=8,pady=(3,7))

            # Left controls all share exactly the same 34x34 geometry.
            left=tk.Frame(controls,bg=HUD_TRANSPARENT_KEY)
            left.pack(side="left")
            def left_square(text,command,font=None):
                holder=tk.Frame(left,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
                holder.pack(side="left",padx=(0,5))
                holder.pack_propagate(False)
                b=self.make_hud_square_button(holder,text,command,size=34,font=font)
                b.place(relx=.5,rely=.5,anchor="center",width=34,height=34)
                return b

            play_pause=left_square("▶",lambda:None,self.ui(11,"bold"))
            try:
                play_pause.place_configure(relx=.5, x=1)
            except Exception:
                pass
            def toggle_timer(tmr=timer,button=play_pause):
                if tmr.running:
                    tmr.stop(); button.config(text="▶")
                else:
                    tmr.start(); button.config(text="⏸")
            play_pause.config(command=toggle_timer)

            def reset_timer(tmr=timer,button=play_pause):
                tmr.reset(); button.config(text="▶")
            reset_btn=left_square("↻",reset_timer,self.ui(14,"bold"))

            def toggle_timer_alert(tmr=timer,button=None):
                tmr.alert_enabled=not tmr.alert_enabled
                if button is not None:
                    button.config(text=("🔔" if tmr.alert_enabled else "🔕"),
                                  fg=("#dcecff" if tmr.alert_enabled else "#6f7885"))
                self.save_timers()
            bell_holder=tk.Frame(controls,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
            bell_holder.pack(side="right")
            bell_holder.pack_propagate(False)
            bell=self.make_hud_square_button(bell_holder,
                    "🔔" if timer.alert_enabled else "🔕",lambda:None,size=34,font=self.ui(10))
            bell.config(fg=("#dcecff" if timer.alert_enabled else "#6f7885"))
            bell.config(command=lambda tmr=timer,b=bell: toggle_timer_alert(tmr,b))
            bell.place(relx=.5,rely=.5,anchor="center",width=34,height=34)

            self.timer_widgets.append((timer,val,finish,play_pause))

        if not self.timer_widgets:
            tk.Label(self.timer_content,text=self.tr(
                "表示中のタイマーはありません。+ で追加・設定できます。",
                "No visible timers. Use + to add or configure."),
                fg="#e1e7ee",bg=HUD_TRANSPARENT_KEY,font=self.ui(9,"bold"),
                justify="center",anchor="center").pack(fill="x",padx=8,pady=12)
        if getattr(self,"timer_panel_visible",False):
            self.root.after_idle(self.fit_window_to_content)

    def tick(self):
        self.poll_network()
        # Capture one shared wall-clock snapshot for this entire UI tick.
        # Normalize to the displayed whole second so the clock and every
        # countdown are calculated from exactly the same second boundary.
        utc=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        shown,label=display_time(utc,self.cfg.get("display_timezone","JST"))
        self.header_canvas.itemconfigure(self.clock_item,text=shown.strftime("%H:%M:%S")+" "+label)
        jst=utc.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        reset=jst.replace(hour=16,minute=0,second=0,microsecond=0)
        if jst>=reset:reset+=datetime.timedelta(days=1)
        reset_utc=reset.astimezone(datetime.timezone.utc)
        reset_show,reset_label=display_time(reset_utc,self.cfg.get("display_timezone","JST"))
        self.header_canvas.itemconfigure(self.daily_item,text=self.tr("デイリー更新 ","Daily Reset ")+reset_show.strftime("%H:%M")+" "+reset_label+"  ("+fmt((reset-jst).total_seconds())+")")
        for e,event_canvas,name_item,status_text,status_time in getattr(self,"event_widgets",[]):
            st,sec,remain=self.event_status(e,jst)
            event_canvas.itemconfigure(name_item,text=self.event_name(e))

            # Event alerts are based on the countdown crossing a boundary, not on
            # entry_minutes. This guarantees an alert at the actual start even when
            # entry countdown is 0.
            key=id(e)
            prev=self.event_alert_state.get(key)
            should_alert=False
            alert_enabled=bool(e.get("alert_enabled",False))
            notify_before=max(0,int(e.get("notify_before_minutes",0) or 0))*60
            alert_timing=e.get("alert_timing","both")  # "both" or "start_only"

            if prev is not None and alert_enabled:
                prev_st,prev_sec=prev

                # Pre-alert: fire once when the "Next" countdown crosses the
                # configured N-minutes-before boundary.
                if alert_timing=="both" and notify_before>0:
                    if prev_st=="next" and st=="next" and prev_sec>notify_before>=sec:
                        should_alert=True

                # Start alert: always fire at the event's actual start.
                # interval/daily with an entry window: next -> entry
                # windows: next -> active
                # weekly or entry_minutes=0: countdown rolls from ~0 to the next occurrence
                start_crossed=False
                if prev_st=="next" and st in ("entry","active"):
                    start_crossed=True
                elif prev_st=="next" and st=="next":
                    # Normal countdown decreases. A large increase means the previous
                    # occurrence just started and event_status() rolled to the next one.
                    if prev_sec<=2 and sec>prev_sec+2:
                        start_crossed=True
                if start_crossed:
                    should_alert=True

            self.event_alert_state[key]=(st,sec)
            if should_alert:
                self.play_event_alert()
            if st=="entry":
                label_txt=self.tr("入場時間","ENTRY TIME")
                time_txt=fmt(sec)
            elif st=="active":
                label_txt=self.tr("● 開催中  残り","● ACTIVE")
                time_txt=fmt(remain)
            else:
                label_txt=self.tr("次回まで","Next")
                time_txt=fmt(sec)
            event_canvas.itemconfigure(status_text,text=label_txt)

            # Color only the time value:
            # - green = the event is currently in an entry/active state
            # - yellow = upcoming event is inside its configured notification window
            # - pale blue = normal countdown
            notify_before=max(0,int(e.get("notify_before_minutes",0) or 0))*60
            active_fg="#78dba2"
            if st in ("entry","active"):
                countdown_fg=active_fg
            elif notify_before>0 and sec<=notify_before:
                countdown_fg="#ffd54a"
            else:
                countdown_fg="#bcdcff"
            event_canvas.itemconfigure(status_time,text=time_txt,fill=countdown_fg)
            bbox=event_canvas.bbox(status_text)
            if bbox:
                event_canvas.coords(status_time,bbox[2]+7,45)
        for t,val,finish,play_pause in getattr(self,"timer_widgets",[]):
            rem,o,e=t.vals(); val.config(text=fmt(rem))
            if t.running and rem<=0 and not t.alert_fired:
                t.alert_fired=True
                if t.alert_enabled:
                    self.play_timer_alert()
            if t.running:
                if play_pause.cget("text")!="⏸️":
                    play_pause.config(text="⏸️")
                finish_utc=utc+datetime.timedelta(seconds=(t.duration-e))
                finish_show,finish_label=display_time(finish_utc,self.cfg.get("display_timezone","JST"))
                finish.config(text=self.tr("終了予定 ","Ends at ")+finish_show.strftime("%H:%M:%S")+" "+finish_label)
            else:
                if play_pause.cget("text")!="▶️":
                    play_pause.config(text="▶️")
                finish.config(text="")
        self.root.after(500,self.tick)

    def on_close(self):
        if getattr(self,'window_maximized',False): self.toggle_window_maximize()
        self.close_ping()
        self.restore_selective_hit_test()
        self._position_restore_in_progress=False
        self.save_window_position()
        try:
            self.save_timers()
        except Exception:
            pass
        self.root.destroy()


    def _finish_position_restore(self):
        self._position_restore_in_progress=False

    def restore_window_position(self):
        """Restore the last main-HUD position from the persistent user store."""
        try:
            x=y=None
            try:
                with open(POSITION_FILE,"r",encoding="utf-8") as f:
                    pos=json.load(f)
                x=pos.get("x"); y=pos.get("y")
            except FileNotFoundError:
                print(f"[AION2 Overlay] No saved window position yet: {POSITION_FILE}")
                return
            except Exception as e:
                print(f"[AION2 Overlay] Window position file read failed: {e}")
                return
            if x is None or y is None:
                return
            x=int(x); y=int(y)

            self.root.update_idletasks()
            ww=max(120,self.root.winfo_reqwidth())
            wh=max(80,self.root.winfo_reqheight())
            try:
                user32=ctypes.windll.user32
                vx=int(user32.GetSystemMetrics(76))
                vy=int(user32.GetSystemMetrics(77))
                vw=max(1,int(user32.GetSystemMetrics(78)))
                vh=max(1,int(user32.GetSystemMetrics(79)))
            except Exception:
                vx=vy=0
                vw=max(1,self.root.winfo_screenwidth())
                vh=max(1,self.root.winfo_screenheight())
            x=max(vx-ww+80,min(x,vx+vw-80))
            y=max(vy,min(y,vy+vh-40))
            self.root.geometry(f"+{x}+{y}")
            self.root.update_idletasks()
            self._last_saved_position=(x,y)
            print(f"[AION2 Overlay] Restored window position x={x}, y={y} source=position_file")
        except Exception as e:
            print(f"[AION2 Overlay] Window position restore failed: {e}")

    def save_window_position(self):
        """Persist the main-HUD X/Y independently of the versioned app folder."""
        try:
            if getattr(self,"_position_restore_in_progress",False):
                return
            if self.root.state() not in ("normal","zoomed"):
                return
            self.root.update_idletasks()
            x=int(self.root.winfo_x()); y=int(self.root.winfo_y())
            if getattr(self,"_last_saved_position",None)==(x,y):
                return
            os.makedirs(POSITION_DIR,exist_ok=True)
            tmp=POSITION_FILE+".tmp"
            with open(tmp,"w",encoding="utf-8") as f:
                json.dump({"x":x,"y":y},f,ensure_ascii=False,indent=2)
            os.replace(tmp,POSITION_FILE)
            self._last_saved_position=(x,y)
            print(f"[AION2 Overlay] Saved window position x={x}, y={y} source=position_file")
        except Exception as e:
            print(f"[AION2 Overlay] Window position save failed: {e}")

    def schedule_window_position_save(self,event=None):
        if getattr(self,"_position_restore_in_progress",False):
            return
        if event is not None and event.widget is not self.root:
            return
        old=getattr(self,"_position_save_after",None)
        if old:
            try:self.root.after_cancel(old)
            except Exception:pass
        self._position_save_after=self.root.after(350,self.save_window_position)


    def _move_handle_start(self,event):
        try:
            self._move_origin=(event.x_root,event.y_root,self.root.winfo_x(),self.root.winfo_y())
        except Exception:
            self._move_origin=None

    def _move_handle_drag(self,event):
        o=getattr(self,"_move_origin",None)
        if not o:return
        try:
            nx=o[2]+event.x_root-o[0]; ny=o[3]+event.y_root-o[1]
            self.root.geometry(f"+{nx}+{ny}")
        except Exception:pass

    def _move_handle_end(self,event=None):
        self._move_origin=None
        self.schedule_window_position_save()

    def make_hud_square_button(self,parent,text,command,size=34,font=None):
        """Consistent square HUD control with a restrained, lighter surface."""
        # Slightly lighter than the old button surface, intentionally low-contrast
        # so controls do not dominate when the HUD background is translucent.
        bg="#26303a"
        active="#34404c"
        b=tk.Button(parent,text=text,command=command,
                    bg=bg,activebackground=active,fg="#f4f7fa",
                    activeforeground="#ffffff",relief="flat",bd=0,
                    highlightthickness=1,highlightbackground="#43505c",
                    highlightcolor="#596878",cursor="hand2",takefocus=0,
                    font=(font or self.ui(11,"bold")))
        # place/pack callers control geometry; width/height are pixel dimensions
        # when place() is used.
        return b

    def build(self):
        for w in self.root.winfo_children(): w.destroy()
        c=self.panel_colors()
        self.root.configure(bg=HUD_TRANSPARENT_KEY)
        self.header=tk.Frame(self.root,bg=HUD_TRANSPARENT_KEY); self.header.pack(fill="x")
        self.header_info=tk.Frame(self.header,bg=HUD_TRANSPARENT_KEY,height=70,width=250)
        self.header_info.pack(side="left",fill="both",expand=True)
        self.header_info.pack_propagate(False)
        self.header_canvas=tk.Canvas(self.header_info,height=70,bg=HUD_TRANSPARENT_KEY,
                                     highlightthickness=0,bd=0)
        self.header_canvas.pack(fill="both",expand=True)
        self.clock_item=self.header_canvas.create_text(
            10,21,text="",anchor="w",fill="white",font=self.ui(18,"bold"))
        self.daily_item=self.header_canvas.create_text(
            10,50,text="",anchor="w",fill="#e2edf7",font=self.ui(10,"bold"))
        # Buttons live in their own right-side row so they never overlap the clock/reset text.
        self.header_buttons=tk.Frame(self.header,bg=HUD_TRANSPARENT_KEY)
        self.header_buttons.pack(side="right",anchor="ne",padx=7,pady=2)
        self.window_controls=tk.Frame(self.header_buttons,bg=HUD_TRANSPARENT_KEY)
        self.window_controls.pack(fill='x',pady=(0,4))
        self.minimize_button=self.make_hud_square_button(self.window_controls,'—',self.minimize_window)
        self.maximize_button=self.make_hud_square_button(self.window_controls,'□',self.toggle_window_maximize)
        self.close_button=self.make_hud_square_button(self.window_controls,'×',self.on_close)
        for btn in (self.minimize_button,self.maximize_button,self.close_button):
            btn.pack(side='left',ipadx=7,ipady=1,padx=1)
        self.close_button.configure(bg='#823139',activebackground='#b43b43')
        self.header_actions=tk.Frame(self.header_buttons,bg=HUD_TRANSPARENT_KEY)
        self.header_actions.pack(fill='x')
        def header_square(text,command):
            holder=tk.Frame(self.header_actions,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
            holder.pack(side="left",padx=2)
            holder.pack_propagate(False)
            btn=self.make_hud_square_button(holder,text,command,size=34)
            btn.place(x=0,y=0,width=34,height=34)
            return btn
        self.stopwatch_button=header_square("⏱",self.show_timer_window)
        # Dedicated move handle for the default frameless/click-through HUD.
        self.move_button=header_square("✥",lambda:None)
        self.move_button.bind("<ButtonPress-1>",self._move_handle_start)
        self.move_button.bind("<B1-Motion>",self._move_handle_drag)
        self.move_button.bind("<ButtonRelease-1>",self._move_handle_end)
        header_square("⚙",self.settings)

        self.build_ping_header(HUD_TRANSPARENT_KEY)

        self.event_section=tk.Frame(self.root,bg=HUD_TRANSPARENT_KEY)
        self.event_section.pack(fill="x",padx=7,pady=(7,3))
        self.event_title=tk.Label(self.event_section,text=self.tr("イベント","EVENTS"),
                                  font=self.ui(10,"bold"),fg="#f5f5f5",
                                  bg=HUD_TRANSPARENT_KEY)
        self.event_title.pack(anchor="w",padx=4,pady=(0,3))
        self.event_box=tk.Frame(self.event_section,bg=HUD_TRANSPARENT_KEY)
        self.event_box.pack(fill="x")
        self.event_widgets=[]
        self.rebuild_event_widgets()
        self.timer_box=tk.Frame(self.root,bg=c["root"])
        self.timer_head=tk.Frame(self.timer_box,bg=c["root"])
        self.timer_head.pack(fill="x",padx=(5,13),pady=(3,1))
        self.timer_title=tk.Label(self.timer_head,text=self.tr("タイマー","TIMERS"),
                                  font=self.ui(10,"bold"),fg="#f5f5f5",
                                  bg=HUD_TRANSPARENT_KEY)
        self.timer_title.pack(side="left")
        self.timer_add_holder=tk.Frame(self.timer_head,bg=HUD_TRANSPARENT_KEY,width=34,height=34)
        self.timer_add_holder.pack(side="right")
        self.timer_add_holder.pack_propagate(False)
        self.timer_add_btn=self.make_hud_square_button(self.timer_add_holder,"+",self.open_timer_settings,size=34)
        self.timer_add_btn.place(x=0,y=0,width=34,height=34)
        self.timer_content=tk.Frame(self.timer_box,bg=c["root"])
        self.timer_content.pack(fill="x")
        self.timer_widgets=[]
        self.timer_panel_visible=False
        self.rebuild_timers()

        self.build_extra_tabs()
        self.apply_frameless_mode()
        self.root.after_idle(self.fit_window_to_content)

    def show_timer_window(self):
        # The clock button opens the editor; keep timer controls visible as well.
        if self.active_tab != 'events': self.show_tab('events')
        if not self.timer_panel_visible: self.toggle_timer_panel()
        self.open_timer_settings()

    def toggle_timer_panel(self):
        if self.active_tab != "events": self.show_tab("events")
        self.timer_panel_visible=not getattr(self,"timer_panel_visible",False)
        if self.timer_panel_visible:
            self.timer_box.pack(fill="x",expand=False,padx=7,pady=3,after=self.event_section)
            self.stopwatch_button.config(relief="sunken")
        else:
            self.timer_box.pack_forget()
            self.stopwatch_button.config(relief="flat")
        self.root.after_idle(self.fit_window_to_content)

    def open_timer_settings(self):
        if not hasattr(self, "_dialog_windows"):
            self._dialog_windows = {}
        existing=self._dialog_windows.get("timer")
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify(); existing.lift()
                return
        except Exception:
            pass
        c=self.panel_colors()
        win=self._new_dialog(self.tr("タイマー設定","Timer Settings"))
        self._dialog_windows["timer"]=win
        def close_dialog():
            self._dialog_windows.pop("timer",None)
            self._safe_dialog_close(win)
        win.protocol("WM_DELETE_WINDOW",close_dialog)
        win.configure(bg=c["root"])
        win.resizable(False,False)

        # Keep this dialog deliberately narrow: the overlay's design language is
        # vertical and compact, not a wide desktop settings sheet.
        outer=tk.Frame(win,bg=c["root"])
        outer.pack(fill="both",expand=True,padx=8,pady=8)

        head=tk.Frame(outer,bg=c["header"],height=38)
        head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head,text=self.tr("タイマー設定","TIMER SETTINGS"),
                 font=self.ui(12,"bold"),fg="white",bg=c["header"]).pack(
                     side="left",padx=9)

        def save_all():
            self.save_timers()
            self.rebuild_timers()
            if getattr(self,"timer_panel_visible",False):
                self.root.after_idle(self.fit_window_to_content)

        def delete_one(timer):
            if timer in self.timers:
                self.timers.remove(timer)
            save_all(); refresh()

        def add_timer():
            self.timers.append(TimerState({
                "name":self.tr("新しいタイマー","New Timer"),
                "duration":300,"visible":False,"alert_enabled":True
            }))
            save_all(); refresh()

        add_holder=tk.Frame(head,bg=c["header"],width=30,height=30)
        add_holder.pack(side="right",padx=5,pady=4); add_holder.pack_propagate(False)
        self.make_hud_square_button(add_holder,"+",add_timer,size=30).place(
            x=0,y=0,width=30,height=30)

        body_wrap=tk.Frame(outer,bg=c["root"])
        body_wrap.pack(fill="both",expand=True,pady=(5,0))
        canvas=tk.Canvas(body_wrap,bg=c["root"],highlightthickness=0,
                         borderwidth=0,width=346,height=360)
        scrollbar=tk.Scrollbar(body_wrap,orient="vertical",command=canvas.yview)
        body=tk.Frame(canvas,bg=c["root"])
        body_id=canvas.create_window((0,0),window=body,anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left",fill="both",expand=True)
        scrollbar.pack(side="right",fill="y")

        def wheel(event):
            d=getattr(event,"delta",0)
            if d: canvas.yview_scroll(-1 if d>0 else 1,"units")
            return "break"
        win.bind("<MouseWheel>",wheel,add="+")
        def bind_wheel(w):
            try: w.bind("<MouseWheel>",wheel,add="+")
            except Exception: pass
            for ch in w.winfo_children(): bind_wheel(ch)

        def sync_scroll(_=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.itemconfigure(body_id,width=canvas.winfo_width())
            except Exception: pass
        body.bind("<Configure>",sync_scroll)
        canvas.bind("<Configure>",sync_scroll)

        def fit_settings():
            # Same outer width as the main Settings dialog.
            # Height follows the timer-card content and is capped; overflow scrolls.
            try:
                win.update_idletasks()
                content_h=max(1, body.winfo_reqheight())
                # header/outer chrome ~= 64px; keep a practical minimum for 1 timer.
                target_h=max(205, min(525, content_h + 64))
            except Exception:
                target_h=360
            self._place_compact_dialog(win,390,target_h)

        def refresh():
            for child in body.winfo_children(): child.destroy()
            if not self.timers:
                tk.Label(body,text=self.tr("タイマーはありません。＋で追加できます。",
                    "No timers. Use + to add one."),fg="#b8c4d0",bg=c["root"],
                    font=self.ui(9,"bold")).pack(fill="x",pady=20)
                win.after_idle(sync_scroll); win.after_idle(fit_settings); return

            for index,timer in enumerate(self.timers,1):
                card=tk.Frame(body,bg=c["card"],highlightthickness=1,
                              highlightbackground="#303842")
                card.pack(fill="x",pady=(0,5))

                # One compact title strip.
                title=tk.Frame(card,bg=c["header"],height=28)
                title.pack(fill="x"); title.pack_propagate(False)
                tk.Label(title,text=f"{self.tr('タイマー','Timer')} {index}",
                         fg="white",bg=c["header"],
                         font=self.ui(9,"bold")).pack(side="left",padx=8)

                inner=tk.Frame(card,bg=c["card"])
                inner.pack(fill="x",padx=8,pady=6)

                # Name and duration use short, dense rows instead of large form blocks.
                name_row=tk.Frame(inner,bg=c["card"]); name_row.pack(fill="x",pady=(0,4))
                tk.Label(name_row,text=self.tr("名称","Name"),fg="#bcdcff",bg=c["card"],
                         font=self.ui(8,"bold"),width=5,anchor="w").pack(side="left")
                name=tk.Entry(name_row,bg=c["header"],fg="white",insertbackground="white",
                              relief="flat",font=self.ui(9))
                name.insert(0,self.localized_timer_name(timer.name))
                name.pack(side="left",fill="x",expand=True,ipady=2)

                time_row=tk.Frame(inner,bg=c["card"]); time_row.pack(fill="x")
                tk.Label(time_row,text=self.tr("時間","Time"),fg="#bcdcff",bg=c["card"],
                         font=self.ui(8,"bold"),width=5,anchor="w").pack(side="left")
                total=max(1,int(timer.duration))
                hv=tk.IntVar(value=total//3600); mv=tk.IntVar(value=(total%3600)//60)
                sv=tk.IntVar(value=total%60)
                controls=tk.Frame(time_row,bg=c["card"]); controls.pack(side="left")
                def spin(var,maximum,unit):
                    box=tk.Frame(controls,bg=c["card"]); box.pack(side="left",padx=(0,3))
                    sp=tk.Spinbox(box,from_=0,to=maximum,textvariable=var,width=2,
                                  bg=c["header"],fg="white",buttonbackground=c["button"],
                                  insertbackground="white",relief="flat",
                                  font=self.mono(9),justify="center")
                    sp.pack(side="left",ipady=1)
                    tk.Label(box,text=unit,fg="#f5f5f5",bg=c["card"],
                             font=self.ui(8)).pack(side="left",padx=(2,0))
                spin(hv,999,self.tr("時","h")); spin(mv,59,self.tr("分","m"))
                spin(sv,59,self.tr("秒","s"))

                # Save/Delete share the same row as the duration controls.
                # This uses the otherwise empty right-hand space and shortens each card.
                actions=tk.Frame(time_row,bg=c["card"])
                actions.pack(side="right",padx=(4,0))
                def apply_one(timer=timer,name=name,hv=hv,mv=mv,sv=sv):
                    try:
                        h=int(hv.get()); m=int(mv.get()); s=int(sv.get())
                        if h<0 or not 0<=m<=59 or not 0<=s<=59: raise ValueError
                        duration=h*3600+m*60+s
                        if duration<=0: raise ValueError
                        timer.name=name.get().strip() or self.tr("タイマー","Timer")
                        timer.duration=duration; timer.visible=True; timer.reset()
                        save_all()
                    except Exception:
                        messagebox.showerror("Error",self.tr(
                            "時間は「時・分・秒」で正しく入力してください。0秒にはできません。",
                            "Enter a valid hours/minutes/seconds duration. Duration cannot be zero."
                        ),parent=win)
                tk.Button(actions,text=self.tr("削除","Delete"),
                          command=lambda timer=timer:delete_one(timer),
                          bg="#4a2929",fg="white",activebackground="#623235",
                          activeforeground="white",relief="flat",cursor="hand2",
                          font=self.ui(8),padx=6,pady=1).pack(side="right")
                tk.Button(actions,text=self.tr("保存","Save"),command=apply_one,
                          bg=c["button"],fg="white",activebackground="#26394d",
                          activeforeground="white",relief="flat",cursor="hand2",
                          font=self.ui(8,"bold"),padx=7,pady=1).pack(
                              side="right",padx=(0,4))

            bind_wheel(body)
            win.after_idle(sync_scroll); win.after_idle(fit_settings)

        refresh()
        win.after_idle(lambda:(fit_settings(),win.deiconify(),win.lift()))

    def settings(self):
        if not hasattr(self, "_dialog_windows"):
            self._dialog_windows = {}
        existing=self._dialog_windows.get("settings")
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify(); existing.lift()
                return
        except Exception:
            pass
        c=self.panel_colors()
        win=self._new_dialog(self.tr("設定","Settings"))
        self._dialog_windows["settings"]=win
        def close_dialog():
            self._dialog_windows.pop("settings",None)
            self._safe_dialog_close(win)
        win.protocol("WM_DELETE_WINDOW",close_dialog)
        win.configure(bg=c["root"])
        win.resizable(False,False)

        outer=tk.Frame(win,bg=c["root"])
        outer.pack(fill="both",expand=True,padx=8,pady=8)
        head=tk.Frame(outer,bg=c["header"]); head.pack(fill="x")
        # Header controls use the same vertical center line.
        head.configure(height=44)
        head.pack_propagate(False)
        tk.Label(head,text=self.tr("設定","SETTINGS"),font=self.ui(13,"bold"),
                 fg="white",bg=c["header"]).pack(side="left",padx=10,fill="y")
        tk.Button(head,text=self.tr("オーバーレイを閉じる","Close Overlay"),
                  bg="#5b2327",activebackground="#743038",
                  fg="white",activeforeground="white",
                  relief="flat",bd=0,font=self.ui(9,"bold"),cursor="hand2",
                  command=self.on_close).pack(side="right",padx=6,pady=7)

        tabs=tk.Frame(outer,bg=c["root"]); tabs.pack(fill="x",pady=(7,4))
        content=tk.Frame(outer,bg=c["root"]); content.pack(fill="both",expand=True)
        pages={}
        tab_buttons={}

        def fit_settings():
            self._place_compact_dialog(win,390,260)

        def show_page(key):
            for k,p in pages.items(): p.pack_forget()
            pages[key].pack(fill="both",expand=True)
            for k,b in tab_buttons.items(): b.config(relief="sunken" if k==key else "flat")
            win.after_idle(fit_settings)

        for key,label in (("events",self.tr("イベント","Events")),("display",self.tr("表示","Display")),("alerts",self.tr("アラート","Alerts")),("info",self.tr("情報","Info"))):
            b=tk.Button(tabs,text=label,bg=c["button"],fg="white",relief="flat",font=self.ui(9,"bold"),command=lambda k=key:show_page(k))
            b.pack(side="left",padx=(0,4)); tab_buttons[key]=b
            pages[key]=tk.Frame(content,bg=c["root"])

        # Events page -- cards matching the overlay rather than a native ttk table.
        ef=pages["events"]
        event_list=tk.Frame(ef,bg=c["root"]); event_list.pack(fill="both",expand=True)
        event_actions=tk.Frame(ef,bg=c["root"]); event_actions.pack(fill="x",pady=(6,0))
        selected={"index":None}

        def refresh_events():
            for w in event_list.winfo_children(): w.destroy()
            selected["index"]=None
            for i,e in enumerate(self.cfg["events"]):
                card=tk.Frame(event_list,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
                card.pack(fill="x",pady=3)
                left=tk.Frame(card,bg=c["card"]); left.pack(side="left",fill="both",expand=True,padx=9,pady=7)
                tk.Label(left,text=self.event_name(e),font=self.ui(10,"bold"),fg="#ffffff",bg=c["card"]).pack(anchor="w")
                state=f'{e.get("type","daily")} / {"ON" if e.get("enabled",True) else "OFF"}'
                tk.Label(left,text=state,font=self.ui(8),fg="#8fa0b5",bg=c["card"]).pack(anchor="w",pady=(2,0))
                actions=tk.Frame(card,bg=c["card"]); actions.pack(side="right",padx=7,pady=7)
                tk.Button(actions,text=self.tr("編集","Edit"),bg=c["button"],fg="white",relief="flat",command=lambda i=i:self.edit_event(win,i,refresh_events)).pack(side="left",padx=2)
                def delete_event(i=i):
                    del self.cfg["events"][i]; save_config(self.cfg); self.rebuild_event_widgets(); refresh_events(); win.after_idle(fit_settings)
                tk.Button(actions,text=self.tr("削除","Delete"),bg="#4a2929",fg="white",relief="flat",command=delete_event).pack(side="left",padx=2)
            win.after_idle(fit_settings)

        tk.Button(event_actions,text="＋ "+self.tr("イベント追加","Add Event"),bg=c["button"],fg="white",relief="flat",command=lambda:self.edit_event(win,None,refresh_events)).pack(side="left")
        refresh_events()

        # Display page -- same charcoal cards/buttons as the main overlay.
        df=pages["display"]
        card=tk.Frame(df,bg=c["card"],highlightthickness=1,highlightbackground="#252c35"); card.pack(fill="x",pady=3)
        form=tk.Frame(card,bg=c["card"]); form.pack(fill="x",padx=10,pady=9)
        def form_label(txt): tk.Label(form,text=txt,font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w",pady=(7,3))
        combo_style={"state":"readonly","font":self.ui(9)}
        form_label("Language")
        lv=tk.StringVar(value="English" if self.cfg.get("language")=="en" else "日本語")
        lbox=ttk.Combobox(form,textvariable=lv,values=["日本語","English"],**combo_style); lbox.pack(fill="x")
        form_label(self.tr("表示時間帯","Display Time Zone"))
        zv=tk.StringVar(value=self.cfg.get("display_timezone","JST")); ttk.Combobox(form,textvariable=zv,values=["JST","PDT","CEST"],**combo_style).pack(fill="x")
        form_label(self.tr("背景の透過度","HUD background opacity"))
        op=tk.Scale(form,from_=20,to=100,orient="horizontal",showvalue=True,bg=c["card"],fg="white",highlightthickness=0,troughcolor=c["header"],activebackground=c["button"],length=360,command=self.preview_background_opacity)
        _op=float(self.cfg.get("background_opacity",.70)); _op=_op/100.0 if _op>1.0 else _op; op.set(int(_op*100)); op.pack(fill="x")
        def apply_display():
            self.cfg["language"]="en" if lv.get()=="English" else "ja"
            self.cfg["display_timezone"]=zv.get()
            self.cfg["background_opacity"]=max(.05,min(1.0,op.get()/100))
            self.cfg.pop("opacity",None)
            save_config(self.cfg)

            # Apply language immediately. Previously the static HUD labels and timer
            # area were only rebuilt after another action (e.g. creating a timer).
            try:
                self.event_title.config(text=self.tr("イベント","EVENTS"))
                self.timer_title.config(text=self.tr("タイマー","TIMERS"))
                self.rebuild_event_widgets()
                self.rebuild_timers()
                self.tick()
            except Exception as exc:
                print(f"[AION2 Overlay] Language refresh warning: {exc}")

            self.apply_main_hud_surface_style()
            self.apply_frameless_mode()
            self.apply_background_opacity()
            win.destroy()
        tk.Button(df,text=self.tr("適用","Apply"),command=apply_display,bg=c["button"],fg="white",relief="flat",font=self.ui(9,"bold")).pack(anchor="e",pady=(6,0))

        # Alerts page
        af=pages["alerts"]
        acard=tk.Frame(af,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        acard.pack(fill="x",pady=3)
        aform=tk.Frame(acard,bg=c["card"]); aform.pack(fill="x",padx=10,pady=10)

        tk.Label(aform,text=self.tr("イベントアラート音量","Event alert volume"),
                 font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w")
        av=tk.Scale(aform,from_=0,to=100,orient="horizontal",showvalue=True,bg=c["card"],fg="white",
                    highlightthickness=0,troughcolor=c["header"],activebackground=c["button"],length=360)
        av.set(int(self.cfg.get("alert_volume",45))); av.pack(fill="x",pady=(3,10))

        tk.Label(aform,text=self.tr("アラート音","Alert sound"),
                 font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w")

        sound_var=tk.StringVar()
        custom_path=self.cfg.get("alert_sound_file","").strip()
        sound_var.set(custom_path if custom_path else self.tr("デフォルト（ソフトチャイム）","Default (soft chime)"))

        sound_row=tk.Frame(aform,bg=c["card"]); sound_row.pack(fill="x",pady=(3,5))
        sound_entry=tk.Entry(sound_row,textvariable=sound_var,state="readonly",
                             readonlybackground=c["header"],fg="white",relief="flat",font=self.ui(9))
        sound_entry.pack(side="left",fill="x",expand=True,ipady=4)

        def choose_sound():
            path=filedialog.askopenfilename(
                parent=win,
                title=self.tr("アラート音を選択","Choose alert sound"),
                filetypes=[(self.tr("音声ファイル","Audio files"),"*.wav *.mp3"),
                           ("WAV","*.wav"),("MP3","*.mp3")]
            )
            if path:
                sound_var.set(path)

        def use_default_sound():
            sound_var.set(self.tr("デフォルト（ソフトチャイム）","Default (soft chime)"))

        tk.Button(sound_row,text=self.tr("参照","Browse"),command=choose_sound,
                  bg=c["button"],fg="white",relief="flat",font=self.ui(9),padx=8).pack(side="left",padx=(6,0))
        tk.Button(sound_row,text=self.tr("既定","Default"),command=use_default_sound,
                  bg=c["button"],fg="white",relief="flat",font=self.ui(9),padx=8).pack(side="left",padx=(4,0))

        tk.Label(aform,text=self.tr(
            "WAV/MP3ファイルを選択できます。\n「既定」で内蔵のソフトチャイムに戻ります。",
            "Choose a WAV or MP3 file, or use Default to return to the built-in soft chime."
        ),font=self.ui(8),fg="#7d8795",bg=c["card"],justify="left",
           anchor="w",wraplength=330).pack(fill="x",pady=(0,8))

        def selected_sound_path():
            v=sound_var.get().strip()
            default_labels={
                "デフォルト（ソフトチャイム）",
                "Default (soft chime)"
            }
            return "" if v in default_labels else v

        alert_actions=tk.Frame(aform,bg=c["card"]); alert_actions.pack(fill="x")

        def preview_alert():
            old_volume=self.cfg.get("alert_volume",45)
            old_sound=self.cfg.get("alert_sound_file","")
            self.cfg["alert_volume"]=av.get()
            self.cfg["alert_sound_file"]=selected_sound_path()
            self.play_event_alert()
            self.cfg["alert_volume"]=old_volume
            self.cfg["alert_sound_file"]=old_sound

        def apply_alerts():
            path=selected_sound_path()
            if path and (not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in (".wav",".mp3")):
                messagebox.showerror(
                    self.tr("音声ファイルエラー","Audio file error"),
                    self.tr("有効なWAVまたはMP3ファイルを選択してください。","Please choose a valid WAV or MP3 file."),
                    parent=win
                )
                return
            self.cfg["alert_volume"]=av.get()
            self.cfg["alert_sound_file"]=path
            save_config(self.cfg)

        tk.Button(alert_actions,text=self.tr("試聴","Preview"),command=preview_alert,
                  bg=c["button"],fg="white",relief="flat",font=self.ui(9),
                  padx=10,pady=3,cursor="hand2").pack(side="left")
        tk.Button(alert_actions,text=self.tr("適用","Apply"),command=apply_alerts,
                  bg=c["button"],fg="white",relief="flat",font=self.ui(9,"bold"),
                  padx=10,pady=3,cursor="hand2").pack(side="right")

        # Timer alerts (independent from event alerts)
        tcard=tk.Frame(af,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        tcard.pack(fill="x",pady=(8,3))
        tf=tk.Frame(tcard,bg=c["card"]); tf.pack(fill="x",padx=10,pady=10)
        tk.Label(tf,text=self.tr("タイマーアラート音量","Timer alert volume"),
                 font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w")
        tav=tk.Scale(tf,from_=0,to=100,orient="horizontal",showvalue=True,bg=c["card"],fg="white",
                     highlightthickness=0,troughcolor=c["header"],activebackground=c["button"],length=360)
        tav.set(int(self.cfg.get("timer_alert_volume",45))); tav.pack(fill="x",pady=(3,10))
        tk.Label(tf,text=self.tr("タイマーアラート音","Timer alert sound"),
                 font=self.ui(9,"bold"),fg="#f5f5f5",bg=c["card"]).pack(anchor="w")
        tsound_var=tk.StringVar()
        tp=self.cfg.get("timer_alert_sound_file","").strip()
        tsound_var.set(tp if tp else self.tr("デフォルト（タイマーチャイム）","Default (timer chime)"))
        tsrow=tk.Frame(tf,bg=c["card"]); tsrow.pack(fill="x",pady=(3,5))
        tse=tk.Entry(tsrow,textvariable=tsound_var,state="readonly",readonlybackground=c["header"],
                     fg="white",relief="flat",font=self.ui(9))
        tse.pack(side="left",fill="x",expand=True,ipady=4)
        def choose_timer_sound():
            path=filedialog.askopenfilename(parent=win,title=self.tr("タイマーアラート音を選択","Choose timer alert sound"),
                filetypes=[(self.tr("音声ファイル","Audio files"),"*.wav *.mp3"),("WAV","*.wav"),("MP3","*.mp3")])
            if path: tsound_var.set(path)
        def default_timer_sound():
            tsound_var.set(self.tr("デフォルト（タイマーチャイム）","Default (timer chime)"))
        tk.Button(tsrow,text=self.tr("参照","Browse"),command=choose_timer_sound,bg=c["button"],fg="white",
                  relief="flat",font=self.ui(9),padx=8).pack(side="left",padx=(6,0))
        tk.Button(tsrow,text=self.tr("既定","Default"),command=default_timer_sound,bg=c["button"],fg="white",
                  relief="flat",font=self.ui(9),padx=8).pack(side="left",padx=(4,0))
        tk.Label(tf,text=self.tr("WAV/MP3ファイルを選択できます。\n「既定」で内蔵のタイマーチャイムに戻ります。",
                                 "Choose a WAV/MP3 file.\nDefault restores the built-in timer chime."),
                 font=self.ui(8),fg="#7d8795",bg=c["card"],justify="left",anchor="w",wraplength=330).pack(fill="x",pady=(0,8))
        def timer_sound_path():
            v=tsound_var.get().strip()
            return "" if v in {"デフォルト（タイマーチャイム）","Default (timer chime)"} else v
        ta=tk.Frame(tf,bg=c["card"]); ta.pack(fill="x")
        def preview_timer_alert():
            ov=self.cfg.get("timer_alert_volume",45); osf=self.cfg.get("timer_alert_sound_file","")
            self.cfg["timer_alert_volume"]=tav.get(); self.cfg["timer_alert_sound_file"]=timer_sound_path()
            self.play_timer_alert()
            self.cfg["timer_alert_volume"]=ov; self.cfg["timer_alert_sound_file"]=osf
        def apply_timer_alert():
            path=timer_sound_path()
            if path and (not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in (".wav",".mp3")):
                messagebox.showerror(self.tr("音声ファイルエラー","Audio file error"),
                                     self.tr("有効なWAVまたはMP3ファイルを選択してください。","Please choose a valid WAV or MP3 file."),parent=win)
                return
            self.cfg["timer_alert_volume"]=tav.get(); self.cfg["timer_alert_sound_file"]=path; save_config(self.cfg)
        tk.Button(ta,text=self.tr("試聴","Preview"),command=preview_timer_alert,bg=c["button"],fg="white",
                  relief="flat",font=self.ui(9),padx=10,pady=3,cursor="hand2").pack(side="left")
        tk.Button(ta,text=self.tr("適用","Apply"),command=apply_timer_alert,bg=c["button"],fg="white",
                  relief="flat",font=self.ui(9,"bold"),padx=10,pady=3,cursor="hand2").pack(side="right")

        # Information page
        inf=pages["info"]
        info_card=tk.Frame(inf,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        info_card.pack(fill="x",pady=3)
        tk.Label(info_card,text="AION2 Event Overlay",
                 font=self.ui(12,"bold"),fg="white",bg=c["card"]).pack(anchor="w",padx=12,pady=(12,3))
        tk.Label(info_card,text=f"Version {APP_VERSION}",
                 font=self.ui(10),fg="#dcecff",bg=c["card"]).pack(anchor="w",padx=12,pady=(0,4))
        # Keep the Japanese notice marker aligned with the first text line.
        # A separate marker column also gives wrapped lines a clean hanging indent.
        if self.cfg.get("language", "ja") == "ja":
            tk.Label(info_card,
                     text="AION2のイベント時刻・タイマー・アラートを表示するオーバーレイです。",
                     font=self.ui(9),fg="#aeb9c7",bg=c["card"],justify="left",wraplength=340
                     ).pack(anchor="w",padx=12,pady=(0,10))
            notices=(
                "ゲーム内部の時刻を直接参照していないため、ゲーム内の時刻と数秒程度の差が生じる場合があります。",
                "本ツールは非公式のコミュニティツールであり、AION2およびNCSOFTの公式ツールではありません。",
            )
            for i, notice in enumerate(notices):
                row=tk.Frame(info_card,bg=c["card"])
                row.pack(fill="x",padx=12,pady=(0,10 if i == 0 else 12))
                tk.Label(row,text="※",font=self.ui(9),fg="#aeb9c7",bg=c["card"],
                         anchor="nw").pack(side="left",anchor="n")
                tk.Label(row,text=notice,font=self.ui(9),fg="#aeb9c7",bg=c["card"],
                         justify="left",wraplength=318,anchor="nw"
                         ).pack(side="left",anchor="n",padx=(5,0))
        else:
            tk.Label(info_card,
                     text=("An overlay for displaying AION2 event schedules, timers, and alerts.\n\n"
                           "Note: This application does not access the game's internal clock, so displayed times may differ from the in-game time by a few seconds.\n\n"
                           "This is an unofficial community tool and is not affiliated with or endorsed by AION2 or NCSOFT."),
                     font=self.ui(9),fg="#aeb9c7",bg=c["card"],justify="left",wraplength=340
                     ).pack(anchor="w",padx=12,pady=(0,12))

        show_page("events")
        def finish_settings_dialog():
            try:
                win.update_idletasks()
                fit_settings()
                win.deiconify()
                win.lift()
            except Exception:
                pass
        win.after_idle(finish_settings_dialog)
        win.after_idle(fit_settings)




    def edit_event(self,parent,index,refresh):
        old=self.cfg["events"][index] if index is not None else {
            "name_ja":"新規イベント","name_en":"New Event","type":"daily",
            "start":"12:00","entry_minutes":0,"notify_before_minutes":0,
            "alert_timing":"both","enabled":True,"alert_enabled":False
        }
        e=json.loads(json.dumps(old))
        c=self.panel_colors()
        w=tk.Toplevel(parent); w.withdraw(); w.title(self.tr("イベント編集","Edit Event"))
        w.configure(bg=c["root"]); w.transient(parent); w.resizable(False,False)

        outer=tk.Frame(w,bg=c["root"]); outer.pack(fill="both",expand=True,padx=9,pady=9)
        head=tk.Frame(outer,bg=c["header"]); head.pack(fill="x")
        tk.Label(head,text=self.tr("イベント編集","EDIT EVENT"),font=self.ui(12,"bold"),
                 fg="white",bg=c["header"]).pack(anchor="w",padx=10,pady=8)

        common=tk.Frame(outer,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        common.pack(fill="x",pady=(7,4))
        ci=tk.Frame(common,bg=c["card"]); ci.pack(fill="x",padx=10,pady=8)
        def lab(p,s):
            tk.Label(p,text=s,fg="#f5f5f5",bg=c["card"],font=self.ui(9,"bold")).pack(anchor="w",pady=(5,2))
        lab(ci,self.tr("日本語名","Japanese name"))
        name_ja=tk.Entry(ci,bg=c["header"],fg="white",insertbackground="white",relief="flat")
        name_ja.insert(0,e.get("name_ja","")); name_ja.pack(fill="x")
        lab(ci,self.tr("英語名","English name"))
        name_en=tk.Entry(ci,bg=c["header"],fg="white",insertbackground="white",relief="flat")
        name_en.insert(0,e.get("name_en","")); name_en.pack(fill="x")
        lab(ci,self.tr("種類","Type"))
        typ=tk.StringVar(value=e.get("type","daily"))
        typebox=ttk.Combobox(ci,textvariable=typ,state="readonly",values=["interval","daily","windows","weekly"])
        typebox.pack(fill="x")
        enabled=tk.BooleanVar(value=e.get("enabled",True))
        tk.Checkbutton(ci,text=self.tr("表示する","Enabled"),variable=enabled,bg=c["card"],fg="white",
                       selectcolor=c["header"],activebackground=c["card"],activeforeground="white").pack(anchor="w",pady=(8,2))

        detail=tk.Frame(outer,bg=c["card"],highlightthickness=1,highlightbackground="#252c35")
        detail.pack(fill="x",pady=4)
        di=tk.Frame(detail,bg=c["card"]); di.pack(fill="x",padx=10,pady=8)
        widgets={}

        def entry(key,title,value):
            lab(di,title)
            x=tk.Entry(di,bg=c["header"],fg="white",insertbackground="white",relief="flat")
            x.insert(0,str(value)); x.pack(fill="x"); widgets[key]=x

        def fit():
            self._place_compact_dialog(w,390,300)

        def rebuild(*_):
            for x in di.winfo_children(): x.destroy()
            widgets.clear()
            t=typ.get()
            if t=="interval":
                entry("start",self.tr("基準開始時刻 HH:MM","Base start HH:MM"),e.get("start","00:00"))
                entry("interval_minutes",self.tr("開催間隔（分）","Interval (minutes)"),e.get("interval_minutes",60))
                entry("entry_minutes",self.tr("入場カウントダウン（分）","Entry countdown (minutes)"),e.get("entry_minutes",0))
            elif t=="daily":
                entry("start",self.tr("開始時刻 HH:MM","Start HH:MM"),e.get("start","12:00"))
                entry("entry_minutes",self.tr("入場カウントダウン（分）","Entry countdown (minutes)"),e.get("entry_minutes",0))
            elif t=="windows":
                entry("windows_text",self.tr("開催時間帯（例 11:00-14:00,19:00-21:00）","Windows (11:00-14:00,19:00-21:00)"),
                      ",".join("-".join(x) for x in e.get("windows",[])))
            elif t=="weekly":
                entry("weekdays_text",self.tr("曜日 0=月…6=日（例 2,5）","Weekdays 0=Mon…6=Sun"),
                      ",".join(map(str,e.get("weekdays",[]))))
                entry("times_text",self.tr("開始時刻（例 21:20,21:50）","Start times (21:20,21:50)"),
                      ",".join(e.get("times",[])))
                entry("entry_minutes",self.tr("入場カウントダウン（分）","Entry countdown (minutes)"),e.get("entry_minutes",0))

            # Alert timing is independent of the entry countdown.
            entry("notify_before_minutes",
                  self.tr("何分前から通知するか（0=事前通知なし）",
                          "Notify before start (minutes, 0=off)"),
                  e.get("notify_before_minutes",0))

            lab(di,self.tr("アラートのタイミング","Alert timing"))
            timing=tk.StringVar(value=e.get("alert_timing","both"))
            timing_box=ttk.Combobox(
                di,state="readonly",textvariable=timing,
                values=["both","start_only"])
            timing_box.pack(fill="x")
            widgets["alert_timing_var"]=timing
            widgets["alert_timing_box"]=timing_box

            timing_help=tk.Label(
                di,
                text=self.tr(
                    "both：設定した分前と開始時刻の両方 / start_only：開始時刻のみ",
                    "both: before-start + start / start_only: start only"),
                fg="#8fa0b4",bg=c["card"],font=self.ui(8),
                justify="left",anchor="w",wraplength=340)
            timing_help.pack(fill="x",pady=(3,2))
            w.after_idle(fit)

        typebox.bind("<<ComboboxSelected>>",rebuild)
        rebuild()

        actions=tk.Frame(outer,bg=c["root"]); actions.pack(fill="x",pady=(6,0))
        def intval(k,minimum=0):
            v=int(widgets[k].get().strip())
            if v<minimum: raise ValueError
            return v

        def save():
            try:
                ne={"name_ja":name_ja.get().strip() or "イベント",
                    "name_en":name_en.get().strip() or "Event",
                    "type":typ.get(),"enabled":enabled.get(),"alert_enabled":bool(old.get("alert_enabled",False))}
                ne["notify_before_minutes"]=intval("notify_before_minutes",0)
                ne["alert_timing"]=widgets["alert_timing_var"].get()
                if ne["alert_timing"] not in ("both","start_only"):
                    ne["alert_timing"]="both"
                t=typ.get()
                if t=="interval":
                    ne["start"]=widgets["start"].get().strip(); parse_hm(ne["start"])
                    ne["interval_minutes"]=intval("interval_minutes",1)
                    ne["entry_minutes"]=intval("entry_minutes",0)
                elif t=="daily":
                    ne["start"]=widgets["start"].get().strip(); parse_hm(ne["start"])
                    ne["entry_minutes"]=intval("entry_minutes",0)
                elif t=="windows":
                    raw=widgets["windows_text"].get().strip()
                    if not raw: raise ValueError
                    ne["windows"]=[]
                    for p in raw.split(","):
                        ab=p.strip().split("-",1)
                        if len(ab)!=2: raise ValueError
                        a,b=ab[0].strip(),ab[1].strip()
                        aa,bb=parse_hm(a),parse_hm(b)
                        if bb<=aa: raise ValueError
                        ne["windows"].append([a,b])
                elif t=="weekly":
                    ne["weekdays"]=[int(x.strip()) for x in widgets["weekdays_text"].get().split(",") if x.strip()]
                    if not ne["weekdays"] or any(x<0 or x>6 for x in ne["weekdays"]): raise ValueError
                    ne["times"]=[x.strip() for x in widgets["times_text"].get().split(",") if x.strip()]
                    if not ne["times"]: raise ValueError
                    for tm in ne["times"]: parse_hm(tm)
                    ne["entry_minutes"]=intval("entry_minutes",0)
            except Exception:
                messagebox.showerror(self.tr("入力エラー","Input error"),
                    self.tr("イベント種類に必要な項目・時刻・数値を確認してください。",
                            "Check the fields, times, and numeric values required for this event type."),parent=w)
                return

            if index is None:self.cfg["events"].append(ne)
            else:self.cfg["events"][index]=ne
            save_config(self.cfg)
            self.event_alert_state.clear()
            self.rebuild_event_widgets()
            self.root.after_idle(self.fit_window_to_content)
            refresh()
            w.destroy()

        tk.Button(actions,text=self.tr("キャンセル","Cancel"),command=w.destroy,bg=c["button"],fg="white",relief="flat").pack(side="right",padx=(4,0))
        tk.Button(actions,text=self.tr("保存","Save"),command=save,bg=c["button"],fg="white",relief="flat",
                  font=self.ui(9,"bold")).pack(side="right")
        def reveal_editor():
            fit()
            w.deiconify()
            w.lift()
        w.after_idle(reveal_editor)


    def save_timers(self):
        self.cfg["timers"]=[{"name":t.name,"duration":t.duration,"visible":t.visible,
                            "alert_enabled":t.alert_enabled} for t in self.timers]; save_config(self.cfg)



if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()

